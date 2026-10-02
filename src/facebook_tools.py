"""
MCP tool definitions and dispatch for Facebook Page posts, comments and insights.

Comment tools also cover Instagram: both platforms use the same Page access token.
"""

from typing import Any, Dict, List

from mcp.types import Tool

from .instagram_client import InstagramClient

PLATFORM = {
    "type": "string",
    "enum": ["facebook", "instagram"],
    "description": "Where the post or comment lives",
}

FACEBOOK_TOOL_DEFS: List[Tool] = [
    Tool(
        name="get_facebook_posts",
        description=(
            "List the Facebook Page's posts with like, comment and share counts. "
            "Set scheduled=true to list posts waiting to be published."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of posts to return (max 100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                },
                "scheduled": {
                    "type": "boolean",
                    "description": "List scheduled posts instead of published ones",
                    "default": False,
                },
            },
        },
    ),
    Tool(
        name="update_facebook_post",
        description="Change the text of an existing Facebook Page post.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "Post ID from get_facebook_posts"},
                "message": {"type": "string", "description": "New text of the post"},
            },
            "required": ["post_id", "message"],
        },
    ),
    Tool(
        name="delete_facebook_post",
        description="Permanently delete a Facebook Page post. This cannot be undone.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "Post ID from get_facebook_posts"},
            },
            "required": ["post_id"],
        },
    ),
    Tool(
        name="get_comments",
        description=(
            "List comments on a Facebook Page post or an Instagram post. "
            "Use the post ID from get_facebook_posts or get_media_posts."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "platform": PLATFORM,
                "post_id": {"type": "string", "description": "Facebook post ID or Instagram media ID"},
                "limit": {
                    "type": "integer",
                    "description": "Number of comments to return (max 100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 25,
                },
            },
            "required": ["platform", "post_id"],
        },
    ),
    Tool(
        name="reply_to_comment",
        description="Reply to a comment on Facebook or Instagram, as the Page or account.",
        inputSchema={
            "type": "object",
            "properties": {
                "platform": PLATFORM,
                "comment_id": {"type": "string", "description": "Comment ID from get_comments"},
                "message": {"type": "string", "description": "Text of the reply"},
            },
            "required": ["platform", "comment_id", "message"],
        },
    ),
    Tool(
        name="hide_comment",
        description=(
            "Hide a Facebook or Instagram comment from the public, or show it again "
            "with hide=false. The comment is not deleted."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "platform": PLATFORM,
                "comment_id": {"type": "string", "description": "Comment ID from get_comments"},
                "hide": {
                    "type": "boolean",
                    "description": "true to hide, false to show again",
                    "default": True,
                },
            },
            "required": ["platform", "comment_id"],
        },
    ),
    Tool(
        name="delete_comment",
        description="Permanently delete a Facebook or Instagram comment. This cannot be undone.",
        inputSchema={
            "type": "object",
            "properties": {
                "platform": PLATFORM,
                "comment_id": {"type": "string", "description": "Comment ID from get_comments"},
            },
            "required": ["platform", "comment_id"],
        },
    ),
    Tool(
        name="like_facebook_comment",
        description="Like a comment on the Facebook Page, as the Page.",
        inputSchema={
            "type": "object",
            "properties": {
                "comment_id": {"type": "string", "description": "Comment ID from get_comments"},
            },
            "required": ["comment_id"],
        },
    ),
    Tool(
        name="get_facebook_page_insights",
        description="Get engagement, views and new-follower figures for the Facebook Page.",
        inputSchema={
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["day", "week", "days_28"],
                    "description": "Time period for the figures",
                    "default": "day",
                },
            },
        },
    ),
    Tool(
        name="get_facebook_post_insights",
        description="Get views, clicks and reactions for one Facebook Page post.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "Post ID from get_facebook_posts"},
            },
            "required": ["post_id"],
        },
    ),
]

# tool name -> usage action counted against the per-hour limit
FACEBOOK_TOOL_ACTIONS: Dict[str, str] = {
    "get_facebook_posts": "facebook_request",
    "update_facebook_post": "facebook_request",
    "delete_facebook_post": "facebook_request",
    "like_facebook_comment": "facebook_request",
    "get_facebook_page_insights": "facebook_request",
    "get_facebook_post_insights": "facebook_request",
    "get_comments": "comment_request",
    "reply_to_comment": "comment_request",
    "hide_comment": "comment_request",
    "delete_comment": "comment_request",
}


async def call_facebook_tool(
    client: InstagramClient, name: str, arguments: Dict[str, Any]
) -> Any:
    """Run one of the tools defined in FACEBOOK_TOOL_DEFS and return its data."""
    if name == "get_facebook_posts":
        return await client.get_facebook_posts(
            arguments.get("limit", 10), arguments.get("scheduled", False)
        )
    if name == "update_facebook_post":
        return await client.update_facebook_post(arguments["post_id"], arguments["message"])
    if name == "delete_facebook_post":
        return await client.delete_object(arguments["post_id"])
    if name == "get_comments":
        return await client.get_comments(
            arguments["platform"], arguments["post_id"], arguments.get("limit", 25)
        )
    if name == "reply_to_comment":
        return await client.reply_to_comment(
            arguments["platform"], arguments["comment_id"], arguments["message"]
        )
    if name == "hide_comment":
        return await client.set_comment_hidden(
            arguments["platform"], arguments["comment_id"], arguments.get("hide", True)
        )
    if name == "delete_comment":
        return await client.delete_object(arguments["comment_id"])
    if name == "like_facebook_comment":
        return await client.like_facebook_comment(arguments["comment_id"])
    if name == "get_facebook_page_insights":
        return await client.get_facebook_page_insights(arguments.get("period", "day"))
    if name == "get_facebook_post_insights":
        return await client.get_facebook_post_insights(arguments["post_id"])
    raise ValueError(f"Unknown Facebook tool: {name}")
