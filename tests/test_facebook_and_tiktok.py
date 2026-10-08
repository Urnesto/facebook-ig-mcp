"""
Unit tests for the Facebook Page, comment and TikTok tools.
"""

import hashlib
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests."""
    settings = MagicMock()
    settings.instagram_api_url = "https://graph.facebook.com/v19.0"
    settings.instagram_access_token = "test_token"
    settings.instagram_business_account_id = "test_account_id"
    settings.rate_limit_requests_per_hour = 200
    settings.cache_enabled = True
    settings.cache_ttl_seconds = 300
    settings.tiktok_client_key = "test_key"
    settings.tiktok_client_secret = "test_secret"

    with patch("src.instagram_client.get_settings", return_value=settings), patch(
        "src.tiktok_client.get_settings", return_value=settings
    ):
        yield settings


from src import tiktok_client
from src.facebook_tools import call_facebook_tool
from src.instagram_client import InstagramAPIError, InstagramClient


@pytest.fixture
def client(mock_settings):
    """Instagram client whose HTTP layer is replaced by a mock."""
    with patch("src.instagram_client.httpx.AsyncClient"):
        client = InstagramClient()
        client._make_request = AsyncMock(return_value={"id": "page_post", "success": True})
        return client


class TestFacebookTools:
    """Request shapes sent to the Graph API."""

    @pytest.mark.asyncio
    async def test_scheduled_post_is_unpublished_with_timestamp(self, client):
        result = await client.publish_facebook_post(
            message="Hello", scheduled_time="2026-10-05T10:00:00+00:00"
        )

        client._make_request.assert_called_once_with(
            "POST",
            "me/feed",
            data={"published": False, "scheduled_publish_time": 1791194400, "message": "Hello"},
        )
        assert result["scheduled_for"] == "2026-10-05T10:00:00+00:00"

    @pytest.mark.asyncio
    async def test_video_post_uses_videos_edge(self, client):
        await client.publish_facebook_post(message="Clip", video_url="https://x.test/v.mp4")

        client._make_request.assert_called_once_with(
            "POST", "me/videos", data={"file_url": "https://x.test/v.mp4", "description": "Clip"}
        )

    @pytest.mark.asyncio
    async def test_post_without_content_is_refused(self, client):
        with pytest.raises(InstagramAPIError):
            await client.publish_facebook_post()

    @pytest.mark.asyncio
    async def test_get_posts_flattens_counts(self, client):
        client._make_request.return_value = {
            "data": [
                {
                    "id": "1_2",
                    "message": "Hi",
                    "likes": {"summary": {"total_count": 3}},
                    "comments": {"summary": {"total_count": 2}},
                    "shares": {"count": 1},
                }
            ]
        }

        posts = await call_facebook_tool(client, "get_facebook_posts", {})

        assert posts == [{"id": "1_2", "message": "Hi", "likes": 3, "comments": 2, "shares": 1}]

    @pytest.mark.parametrize(
        "platform, endpoint, field",
        [("facebook", "c1/comments", "is_hidden"), ("instagram", "c1/replies", "hide")],
    )
    @pytest.mark.asyncio
    async def test_reply_and_hide_use_platform_edges(self, client, platform, endpoint, field):
        await call_facebook_tool(
            client, "reply_to_comment", {"platform": platform, "comment_id": "c1", "message": "Thanks"}
        )
        client._make_request.assert_called_with("POST", endpoint, data={"message": "Thanks"})

        await call_facebook_tool(client, "hide_comment", {"platform": platform, "comment_id": "c1"})
        client._make_request.assert_called_with("POST", "c1", data={field: True})

    @pytest.mark.asyncio
    async def test_facebook_reply_can_carry_a_gif(self, client):
        gif = "https://giphy.com/gifs/abc"
        await call_facebook_tool(
            client, "reply_to_comment", {"platform": "facebook", "comment_id": "c1", "gif_url": gif}
        )
        client._make_request.assert_called_with(
            "POST", "c1/comments", data={"attachment_share_url": gif}
        )

        with pytest.raises(InstagramAPIError):
            await call_facebook_tool(
                client, "reply_to_comment", {"platform": "instagram", "comment_id": "c1", "gif_url": gif}
            )

    @pytest.mark.asyncio
    async def test_delete_tools_send_delete(self, client):
        await call_facebook_tool(client, "delete_facebook_post", {"post_id": "1_2"})
        client._make_request.assert_called_with("DELETE", "1_2")

        await call_facebook_tool(
            client, "delete_comment", {"platform": "instagram", "comment_id": "c9"}
        )
        client._make_request.assert_called_with("DELETE", "c9")


class TestTikTok:
    """TikTok upload planning, PKCE and request bodies."""

    def test_code_challenge_is_hex_sha256(self):
        assert tiktok_client.code_challenge("abc") == hashlib.sha256(b"abc").hexdigest()

    @pytest.mark.parametrize(
        "size, expected",
        [
            (4 * tiktok_client.MB, (4 * tiktok_client.MB, 1)),
            (64 * tiktok_client.MB, (64 * tiktok_client.MB, 1)),
            (100 * tiktok_client.MB, (32 * tiktok_client.MB, 3)),
            (65 * tiktok_client.MB, (32 * tiktok_client.MB, 2)),
        ],
    )
    def test_plan_chunks(self, size, expected):
        assert tiktok_client.plan_chunks(size) == expected

    @pytest.mark.asyncio
    async def test_publish_video_from_file(self, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"0" * 1000)
        api = AsyncMock(
            side_effect=[
                {"privacy_level_options": ["SELF_ONLY"]},
                {"publish_id": "v_pub_1", "upload_url": "https://upload.test/u"},
            ]
        )
        upload = AsyncMock()

        with patch.object(tiktok_client, "_api", api), patch.object(tiktok_client, "_upload", upload):
            result = await tiktok_client.publish_video(title="Hi", video_path=str(video))

        init_path, init_body = api.call_args_list[1].args
        assert init_path == "post/publish/video/init/"
        assert init_body["source_info"] == {
            "source": "FILE_UPLOAD",
            "video_size": 1000,
            "chunk_size": 1000,
            "total_chunk_count": 1,
        }
        assert init_body["post_info"]["privacy_level"] == "SELF_ONLY"
        upload.assert_awaited_once_with("https://upload.test/u", video, 1000, 1)
        assert result == {"publish_id": "v_pub_1", "privacy_level": "SELF_ONLY"}

    @pytest.mark.asyncio
    async def test_unavailable_privacy_level_is_refused(self):
        api = AsyncMock(return_value={"privacy_level_options": ["SELF_ONLY"]})

        with patch.object(tiktok_client, "_api", api):
            with pytest.raises(tiktok_client.TikTokError, match="PUBLIC_TO_EVERYONE"):
                await tiktok_client.publish_video(
                    title="Hi",
                    video_url="https://x.test/v.mp4",
                    privacy_level="PUBLIC_TO_EVERYONE",
                )

        assert api.await_count == 1

    @pytest.mark.asyncio
    async def test_upload_sends_content_range_per_chunk(self, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"a" * 10 + b"b" * 13)
        http = MagicMock()
        http.put = AsyncMock(side_effect=[MagicMock(status_code=206), MagicMock(status_code=201)])
        http.__aenter__ = AsyncMock(return_value=http)
        http.__aexit__ = AsyncMock(return_value=False)

        with patch.object(tiktok_client.httpx, "AsyncClient", return_value=http):
            await tiktok_client._upload("https://upload.test/u", video, 10, 2)

        first, second = http.put.call_args_list
        assert first.kwargs["headers"]["Content-Range"] == "bytes 0-9/23"
        assert first.kwargs["content"] == b"a" * 10
        assert second.kwargs["headers"]["Content-Range"] == "bytes 10-22/23"
        assert second.kwargs["content"] == b"b" * 13

    @pytest.mark.asyncio
    async def test_expired_token_is_refreshed(self, tmp_path):
        token_path = tmp_path / "tiktok_token.json"
        token_path.write_text(
            json.dumps(
                {
                    "access_token": "old",
                    "refresh_token": "rft",
                    "expires_at": time.time() - 10,
                    "refresh_expires_at": time.time() + 1000,
                }
            )
        )
        refresh = AsyncMock(return_value={"access_token": "new"})

        with patch.object(tiktok_client, "TOKEN_PATH", token_path), patch.object(
            tiktok_client, "_token_request", refresh
        ):
            assert await tiktok_client._access_token() == "new"

        refresh.assert_awaited_once_with({"grant_type": "refresh_token", "refresh_token": "rft"})

    @pytest.mark.asyncio
    async def test_not_logged_in_gives_clear_error(self, tmp_path):
        with patch.object(tiktok_client, "TOKEN_PATH", tmp_path / "missing.json"):
            with pytest.raises(tiktok_client.TikTokError, match="Not logged in"):
                await tiktok_client._access_token()
