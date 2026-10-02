"""
Follower list export and DMs via instagrapi (unofficial - Meta's Graph API has no
followers endpoint and only allows DM replies).

Logs in with INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD and caches the session in
data/ so later calls reuse it instead of logging in again.

Every follower fetch and DM is recorded in data/usage_<username>.json, which is
used to enforce the configured 24-hour limits and to avoid DMing a user twice.
"""

import asyncio
import csv
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from .usage import DATA_DIR, check_limit, load_events, record_event

logger = structlog.get_logger(__name__)

CSV_FIELDS = ["user_id", "username", "full_name", "is_private", "is_verified"]

_client: Any = None
_client_username: Optional[str] = None


class UnofficialAPIError(Exception):
    """Raised when the unofficial Instagram API cannot complete a request."""


def _refuse_challenge_code(username: str, choice: Any) -> str:
    # instagrapi's default handler calls input(), which would read the MCP stdio stream
    raise UnofficialAPIError(
        f"Instagram sent a verification code for '{username}'. Log in once from a "
        "terminal to enter it: .venv/bin/python -m src.unofficial_client"
    )


def _get_client(username: str, password: str, interactive: bool = False) -> Any:
    """Return a logged-in instagrapi client, reusing the saved session when possible."""
    global _client, _client_username
    if _client is not None and _client_username == username:
        return _client

    try:
        from instagrapi import Client
        from instagrapi.exceptions import (
            BadPassword,
            ChallengeRequired,
            LoginRequired,
            TwoFactorRequired,
        )
    except ImportError as e:
        raise UnofficialAPIError(
            "instagrapi is not installed. Run: uv pip install instagrapi"
        ) from e

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session_path = DATA_DIR / f"session_{username}.json"

    client = Client()
    if not interactive:
        client.challenge_code_handler = _refuse_challenge_code
    try:
        if session_path.exists():
            client.load_settings(session_path)
            client.login(username, password)
            try:
                client.get_timeline_feed()
            except LoginRequired:
                # Saved session expired: log in again, keeping the same device IDs
                logger.info("Saved session expired, logging in again", username=username)
                uuids = client.get_settings().get("uuids", {})
                client.set_settings({})
                client.set_uuids(uuids)
                client.login(username, password)
        else:
            client.login(username, password)
    except BadPassword as e:
        raise UnofficialAPIError(
            "Instagram rejected INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD"
        ) from e
    except TwoFactorRequired as e:
        raise UnofficialAPIError(
            "Account has two-factor authentication enabled, which this login does not support"
        ) from e
    except ChallengeRequired as e:
        raise UnofficialAPIError(
            "Instagram wants a security check. Open the Instagram app, approve the "
            "login attempt, then try again"
        ) from e

    client.dump_settings(session_path)
    _client, _client_username = client, username
    return client


def _refuse_repeat_dm(
    login_username: str, user_id: Optional[str], username: Optional[str]
) -> None:
    for e in reversed(load_events(login_username)):
        if e["action"] != "dm":
            continue
        if (user_id and e.get("user_id") == str(user_id)) or (
            username and e.get("username") == username
        ):
            raise UnofficialAPIError(
                f"Already sent a DM to {username or user_id} on {e['at']}. "
                "Pass allow_repeat=true to message them again"
            )


def _fetch_followers(
    login_username: str, password: str, target_username: str, daily_limit: int
) -> List[Dict[str, Any]]:
    check_limit(login_username, "follower_fetch", daily_limit)
    client = _get_client(login_username, password)
    if target_username == login_username:
        user_id = str(client.user_id)
    else:
        user_id = client.user_id_from_username(target_username)

    followers = [
        {
            "user_id": str(f.pk),
            "username": f.username,
            "full_name": f.full_name,
            "is_private": f.is_private,
            "is_verified": f.is_verified,
        }
        for f in client.user_followers(user_id, use_cache=False).values()
    ]
    record_event(
        login_username, "follower_fetch", target=target_username, total=len(followers)
    )
    return followers


def _send_dm(
    login_username: str,
    password: str,
    message: str,
    username: Optional[str],
    user_id: Optional[str],
    daily_limit: int,
    allow_repeat: bool,
) -> Dict[str, Any]:
    check_limit(login_username, "dm", daily_limit)
    # Check the log before touching Instagram, then again once the ID is resolved
    if not allow_repeat:
        _refuse_repeat_dm(login_username, user_id, username)
    client = _get_client(login_username, password)
    if not user_id:
        user_id = str(client.user_id_from_username(username))
        if not allow_repeat:
            _refuse_repeat_dm(login_username, user_id, username)
    user_id = str(user_id)

    sent = client.direct_send(message, user_ids=[int(user_id)])
    record_event(
        login_username,
        "dm",
        user_id=user_id,
        username=username,
        message=message,
        message_id=str(sent.id),
    )
    return {
        "message_id": str(sent.id),
        "thread_id": str(sent.thread_id) if sent.thread_id else None,
        "recipient_user_id": user_id,
        "recipient_username": username,
    }


async def get_followers(
    login_username: str,
    password: str,
    target_username: Optional[str] = None,
    only_new: bool = False,
    daily_limit: int = 10,
) -> Dict[str, Any]:
    """Fetch followers, save CSV + JSON snapshot, and diff against the previous snapshot."""
    target_username = target_username or login_username
    followers = await asyncio.to_thread(
        _fetch_followers, login_username, password, target_username, daily_limit
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = DATA_DIR / f"followers_{target_username}.json"
    csv_path = DATA_DIR / f"followers_{target_username}.csv"

    previous: Dict[str, Any] = {}
    if snapshot_path.exists():
        previous = json.loads(snapshot_path.read_text(encoding="utf-8"))
    previous_followers = previous.get("followers", [])

    prev_ids = {f["user_id"] for f in previous_followers}
    current_ids = {f["user_id"] for f in followers}
    new_followers = [f for f in followers if f["user_id"] not in prev_ids]
    lost_followers = [f for f in previous_followers if f["user_id"] not in current_ids]

    checked_at = datetime.utcnow().isoformat()
    snapshot_path.write_text(
        json.dumps({"checked_at": checked_at, "followers": followers}, indent=2),
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(followers)

    logger.info("Followers fetched", target=target_username, total=len(followers))

    return {
        "username": target_username,
        "total": len(followers),
        "previous_check": previous.get("checked_at"),
        "new_since_last_check": new_followers,
        "lost_since_last_check": lost_followers,
        "followers": new_followers if only_new else followers,
        "csv_path": str(csv_path),
        "checked_at": checked_at,
    }


async def send_dm_to_user(
    login_username: str,
    password: str,
    message: str,
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    daily_limit: int = 20,
    allow_repeat: bool = False,
) -> Dict[str, Any]:
    """Send a DM to a user identified by username or by a user_id from get_followers."""
    if not username and not user_id:
        raise UnofficialAPIError("Provide either username or user_id")
    return await asyncio.to_thread(
        _send_dm,
        login_username,
        password,
        message,
        username,
        user_id,
        daily_limit,
        allow_repeat,
    )


if __name__ == "__main__":
    # One-time interactive login: prompts for the emailed/SMS code if Instagram asks
    from .config import get_settings

    settings = get_settings()
    if not settings.instagram_username or not settings.instagram_password:
        raise SystemExit("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set in .env")
    _get_client(settings.instagram_username, settings.instagram_password, interactive=True)
    print(f"Logged in as {settings.instagram_username}; session saved in {DATA_DIR}")
