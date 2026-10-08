# Commands

Everything Claude can do with this server. You do not type the command name.
Just ask Claude in plain words, like the examples in the last column.

## Instagram

| Command | What it does | Example |
|---|---|---|
| `get_profile_info` | Shows your username, follower count and number of posts | "Show my Instagram profile" |
| `get_media_posts` | Lists your posts with likes and comment counts | "Show my last 5 Instagram posts" |
| `get_media_insights` | Shows reach, likes, comments, shares and saves for one post | "How did my last post do?" |
| `get_account_insights` | Shows reach, profile visits and website clicks for the account | "Show my Instagram stats for today" |
| `publish_media` | Publishes a photo or video with a caption | "Post this image to Instagram with the caption ..." |
| `get_followers` | Lists your followers and who is new or gone since last time | "Get my follower list" |
| `get_conversations` | Lists your direct message conversations | "Check my Instagram DMs" |
| `get_conversation_messages` | Shows the messages in one conversation | "Open the conversation with ..." |
| `send_dm` | Replies to someone who messaged you in the last 24 hours | "Reply to that DM with ..." |
| `send_dm_to_user` | Sends a direct message to any user | "Send a DM to @username saying ..." |

## Comments (Instagram and Facebook)

| Command | What it does | Example |
|---|---|---|
| `get_comments` | Lists the comments on a post | "Show the comments on my last post" |
| `reply_to_comment` | Replies to a comment | "Reply to that comment with ..." |
| `hide_comment` | Hides a comment from the public, or shows it again | "Hide all comments on my last post" |
| `delete_comment` | Deletes a comment for good | "Delete that comment" |
| `like_facebook_comment` | Likes a comment as your Facebook Page | "Like that Facebook comment" |

## Facebook Page

| Command | What it does | Example |
|---|---|---|
| `get_account_pages` | Shows the Facebook Page and the Instagram account linked to it | "Which Page is connected?" |
| `get_facebook_posts` | Lists the Page's posts, or the scheduled ones | "Show my Facebook posts" |
| `publish_facebook_post` | Publishes text, a link, a photo or a video, now or at a set time | "Post this to Facebook tomorrow at 10:00" |
| `update_facebook_post` | Changes the text of a post | "Change the text of my last Facebook post to ..." |
| `delete_facebook_post` | Deletes a post for good | "Delete my last Facebook post" |
| `get_facebook_post_insights` | Shows views, clicks and reactions for one post | "How did my last Facebook post do?" |
| `get_facebook_page_insights` | Shows engagement, views and new followers for the Page | "Show my Facebook Page stats for this week" |

## TikTok

| Command | What it does | Example |
|---|---|---|
| `tiktok_get_creator_info` | Shows the connected TikTok account and what it is allowed to post | "Which TikTok account is connected?" |
| `tiktok_publish_video` | Posts a video from a file on your computer | "Post this video to TikTok with the title ..." |
| `tiktok_publish_photos` | Posts one or more photos | "Post these photos to TikTok" |
| `tiktok_get_post_status` | Checks whether a TikTok post finished publishing | "Did my TikTok post go through?" |

## Checks

| Command | What it does | Example |
|---|---|---|
| `validate_access_token` | Checks that the Instagram and Facebook connection still works | "Is my Instagram connection working?" |
| `get_usage` | Shows how many posts, messages and requests you have used today | "How many posts do I have left today?" |

## Good to know

- Photos and videos for Instagram and Facebook must be at a public web address. Claude cannot upload a file straight from your computer to them.
- TikTok videos are uploaded from a file on your computer. TikTok photos only work from a website you have verified with TikTok.
- TikTok posts are private (only you can see them) until TikTok has approved the app.
- Instagram posts cannot be edited or deleted from here. Do that in the Instagram app.
- Deleting a post or a comment cannot be undone.
- `get_followers` and `send_dm_to_user` use an unofficial login. If Instagram rejects it, they stop working until the `instagrapi` library is updated.
- `get_conversations` only shows messages if "Allow access to messages" is turned on in the Instagram app.
- After any change to the code or to `.env`, reconnect with `/mcp`.
