"""
TikTok posting via the official Content Posting API.

Needs a TikTok developer app with Login Kit and the Content Posting API (Direct
Post) added. Log in once with:
    .venv/bin/python -m src.tiktok_client
The tokens are saved in data/tiktok_token.json and refreshed automatically.

Until TikTok has audited the app, every post is restricted to private viewing.
"""

import asyncio
import hashlib
import json
import mimetypes
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import structlog
from mcp.types import Tool

from .config import get_settings
from .usage import DATA_DIR

logger = structlog.get_logger(__name__)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
API_URL = "https://open.tiktokapis.com/v2"
TOKEN_PATH = DATA_DIR / "tiktok_token.json"

MB = 1024 * 1024
MAX_SINGLE_UPLOAD = 64 * MB
CHUNK_SIZE = 32 * MB


class TikTokError(Exception):
    """Raised when the TikTok API cannot complete a request."""


def code_challenge(verifier: str) -> str:
    """TikTok's desktop PKCE uses the hex SHA256 of the verifier, not base64url."""
    return hashlib.sha256(verifier.encode()).hexdigest()


def plan_chunks(video_size: int) -> Tuple[int, int]:
    """Return (chunk_size, total_chunk_count) following TikTok's chunk rules."""
    if video_size <= MAX_SINGLE_UPLOAD:
        return video_size, 1
    # Trailing bytes are merged into the final chunk, which may exceed chunk_size
    return CHUNK_SIZE, video_size // CHUNK_SIZE


def _credentials() -> Tuple[str, str]:
    settings = get_settings()
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise TikTokError("TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET must be set in .env")
    return settings.tiktok_client_key, settings.tiktok_client_secret


def _save_token(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "access_token" not in payload:
        raise TikTokError(
            f"TikTok login failed: {payload.get('error_description') or payload}"
        )
    now = time.time()
    token = {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": now + payload["expires_in"],
        "refresh_expires_at": now + payload["refresh_expires_in"],
        "open_id": payload.get("open_id"),
        "scope": payload.get("scope"),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(token, indent=2), encoding="utf-8")
    return token


async def _token_request(form: Dict[str, str]) -> Dict[str, Any]:
    client_key, client_secret = _credentials()
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            TOKEN_URL,
            data={"client_key": client_key, "client_secret": client_secret, **form},
        )
    return _save_token(response.json())


async def _access_token() -> str:
    if not TOKEN_PATH.exists():
        raise TikTokError(
            "Not logged in to TikTok. Run once: .venv/bin/python -m src.tiktok_client"
        )
    token = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    if token["expires_at"] - time.time() < 300:
        # Access tokens last 24 hours; the refresh token lasts a year
        if token["refresh_expires_at"] < time.time():
            raise TikTokError(
                "TikTok login expired. Run again: .venv/bin/python -m src.tiktok_client"
            )
        token = await _token_request(
            {"grant_type": "refresh_token", "refresh_token": token["refresh_token"]}
        )
    return token["access_token"]


async def _api(path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    token = await _access_token()
    async with httpx.AsyncClient(timeout=60) as http:
        response = await http.post(
            f"{API_URL}/{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=body or {},
        )
    payload = response.json()
    error = payload.get("error") or {}
    if error.get("code", "ok") != "ok":
        raise TikTokError(f"TikTok API error ({error['code']}): {error.get('message', '')}")
    return payload.get("data", {})


async def get_creator_info() -> Dict[str, Any]:
    """Account name and the privacy levels and limits TikTok allows for it right now."""
    return await _api("post/publish/creator_info/query/")


async def _check_privacy(privacy_level: str) -> None:
    options = (await get_creator_info()).get("privacy_level_options", [])
    if privacy_level not in options:
        raise TikTokError(
            f"Privacy level {privacy_level} is not available for this account. "
            f"Allowed: {', '.join(options)}"
        )


async def _upload(upload_url: str, path: Path, chunk_size: int, chunks: int) -> None:
    size = path.stat().st_size
    mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
    async with httpx.AsyncClient(timeout=600) as http:
        with path.open("rb") as fh:
            for index in range(chunks):
                first = index * chunk_size
                last = size - 1 if index == chunks - 1 else first + chunk_size - 1
                fh.seek(first)
                response = await http.put(
                    upload_url,
                    content=fh.read(last - first + 1),
                    headers={
                        "Content-Type": mime,
                        "Content-Range": f"bytes {first}-{last}/{size}",
                    },
                )
                if response.status_code not in (201, 206):
                    raise TikTokError(
                        f"Video upload failed at chunk {index + 1}/{chunks} "
                        f"(HTTP {response.status_code})"
                    )


async def publish_video(
    title: str,
    video_path: Optional[str] = None,
    video_url: Optional[str] = None,
    privacy_level: str = "SELF_ONLY",
    disable_comment: bool = False,
    disable_duet: bool = False,
    disable_stitch: bool = False,
) -> Dict[str, Any]:
    """Post a video from a local file or from a URL on a domain verified with TikTok."""
    if bool(video_path) == bool(video_url):
        raise TikTokError("Provide exactly one of video_path or video_url")
    await _check_privacy(privacy_level)

    post_info = {
        "title": title,
        "privacy_level": privacy_level,
        "disable_comment": disable_comment,
        "disable_duet": disable_duet,
        "disable_stitch": disable_stitch,
    }
    if video_url:
        source_info: Dict[str, Any] = {"source": "PULL_FROM_URL", "video_url": video_url}
    else:
        path = Path(video_path).expanduser()
        if not path.is_file():
            raise TikTokError(f"Video file not found: {path}")
        chunk_size, chunks = plan_chunks(path.stat().st_size)
        source_info = {
            "source": "FILE_UPLOAD",
            "video_size": path.stat().st_size,
            "chunk_size": chunk_size,
            "total_chunk_count": chunks,
        }

    data = await _api(
        "post/publish/video/init/", {"post_info": post_info, "source_info": source_info}
    )
    if not video_url:
        await _upload(data["upload_url"], path, chunk_size, chunks)

    logger.info("TikTok video submitted", publish_id=data["publish_id"])
    return {"publish_id": data["publish_id"], "privacy_level": privacy_level}


async def publish_photos(
    photo_urls: List[str],
    title: str,
    description: str = "",
    privacy_level: str = "SELF_ONLY",
    disable_comment: bool = False,
    auto_add_music: bool = True,
) -> Dict[str, Any]:
    """Post one or more photos. The URLs must be on a domain verified with TikTok."""
    if not photo_urls:
        raise TikTokError("Provide at least one photo URL")
    await _check_privacy(privacy_level)

    data = await _api(
        "post/publish/content/init/",
        {
            "post_info": {
                "title": title,
                "description": description,
                "privacy_level": privacy_level,
                "disable_comment": disable_comment,
                "auto_add_music": auto_add_music,
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_cover_index": 0,
                "photo_images": photo_urls,
            },
            "post_mode": "DIRECT_POST",
            "media_type": "PHOTO",
        },
    )
    logger.info("TikTok photos submitted", publish_id=data["publish_id"])
    return {"publish_id": data["publish_id"], "privacy_level": privacy_level}


async def get_post_status(publish_id: str) -> Dict[str, Any]:
    """Check whether a submitted post is still processing, published or failed."""
    return await _api("post/publish/status/fetch/", {"publish_id": publish_id})


PRIVACY = {
    "type": "string",
    "enum": ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"],
    "description": (
        "Who can see the post. Only SELF_ONLY works until TikTok has audited the app."
    ),
    "default": "SELF_ONLY",
}

TIKTOK_TOOL_DEFS: List[Tool] = [
    Tool(
        name="tiktok_get_creator_info",
        description=(
            "Show the connected TikTok account and which privacy levels and video "
            "length TikTok currently allows for posting."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="tiktok_publish_video",
        description=(
            "Post a video to TikTok (official Content Posting API) from a local file or "
            "from a URL on a domain verified with TikTok. Posts are private (SELF_ONLY) "
            "until TikTok has audited the app. Returns a publish_id to check with "
            "tiktok_get_post_status."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Caption of the video, may include #hashtags and @mentions",
                },
                "video_path": {
                    "type": "string",
                    "description": "Path to a video file on this computer (mp4, mov or webm)",
                },
                "video_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "URL of the video, on a domain verified with TikTok",
                },
                "privacy_level": PRIVACY,
                "disable_comment": {"type": "boolean", "default": False},
                "disable_duet": {"type": "boolean", "default": False},
                "disable_stitch": {"type": "boolean", "default": False},
            },
            "required": ["title"],
        },
    ),
    Tool(
        name="tiktok_publish_photos",
        description=(
            "Post one or more photos to TikTok (official Content Posting API). The photo "
            "URLs must be on a domain verified with TikTok. Posts are private (SELF_ONLY) "
            "until TikTok has audited the app."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "photo_urls": {
                    "type": "array",
                    "items": {"type": "string", "format": "uri"},
                    "description": "URLs of the photos; the first one is the cover",
                },
                "title": {"type": "string", "description": "Title of the post"},
                "description": {"type": "string", "description": "Caption text"},
                "privacy_level": PRIVACY,
                "disable_comment": {"type": "boolean", "default": False},
                "auto_add_music": {"type": "boolean", "default": True},
            },
            "required": ["photo_urls", "title"],
        },
    ),
    Tool(
        name="tiktok_get_post_status",
        description="Check whether a TikTok post is still processing, published or failed.",
        inputSchema={
            "type": "object",
            "properties": {
                "publish_id": {
                    "type": "string",
                    "description": "publish_id returned by a tiktok_publish tool",
                },
            },
            "required": ["publish_id"],
        },
    ),
]

# tool name -> usage action; only publishing counts against the daily limit
TIKTOK_TOOL_ACTIONS: Dict[str, str] = {
    "tiktok_publish_video": "tiktok_post",
    "tiktok_publish_photos": "tiktok_post",
}
TIKTOK_TOOL_NAMES = {tool.name for tool in TIKTOK_TOOL_DEFS}


async def call_tiktok_tool(name: str, arguments: Dict[str, Any]) -> Any:
    """Run one of the tools defined in TIKTOK_TOOL_DEFS and return its data."""
    if name == "tiktok_get_creator_info":
        return await get_creator_info()
    if name == "tiktok_publish_video":
        return await publish_video(**arguments)
    if name == "tiktok_publish_photos":
        return await publish_photos(**arguments)
    if name == "tiktok_get_post_status":
        return await get_post_status(arguments["publish_id"])
    raise ValueError(f"Unknown TikTok tool: {name}")


def _wait_for_callback(redirect_uri: str) -> Dict[str, str]:
    """Serve the redirect URI once and return the query parameters TikTok sends."""
    target = urlparse(redirect_uri)
    received: Dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            received.update(
                {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>TikTok login received. You can close this window.</h2>")

        def log_message(self, *args: Any) -> None:
            pass

    with HTTPServer((target.hostname, target.port), Handler) as server:
        while "code" not in received and "error" not in received:
            server.handle_request()
    return received


def login() -> None:
    """One-time interactive login: opens TikTok in the browser and saves the tokens."""
    settings = get_settings()
    client_key, _ = _credentials()
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)

    url = AUTH_URL + "?" + urlencode(
        {
            "client_key": client_key,
            "scope": settings.tiktok_scopes,
            "response_type": "code",
            "redirect_uri": settings.tiktok_redirect_uri,
            "state": state,
            "code_challenge": code_challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    print("Opening TikTok in your browser. If it does not open, visit:\n" + url)
    webbrowser.open(url)

    received = _wait_for_callback(settings.tiktok_redirect_uri)
    if "error" in received:
        raise SystemExit(
            f"TikTok refused the login: {received.get('error_description', received['error'])}"
        )
    if received.get("state") != state:
        raise SystemExit("Login cancelled: the response did not match this login attempt.")

    asyncio.run(
        _token_request(
            {
                "grant_type": "authorization_code",
                "code": received["code"],
                "redirect_uri": settings.tiktok_redirect_uri,
                "code_verifier": verifier,
            }
        )
    )
    print(f"Logged in to TikTok; tokens saved in {TOKEN_PATH}")


if __name__ == "__main__":
    try:
        login()
    except TikTokError as e:
        raise SystemExit(str(e))
