# Instructions for Claude: setting up and helping with this project

This repository is an MCP server that lets Claude work with an Instagram account, its Facebook Page and a TikTok account. Most people who use it are not programmers. Your job is to get them set up and then operate the tools for them.

Download source: https://github.com/Urnesto/facebook-ig-mcp.git

## How to talk to the user

- Assume no technical background. Give one step at a time, say exactly where to click, and give the direct link.
- `SETUP_GUIDE.md` is the user-facing guide, with a screenshot for every click. Point to its step numbers ("step 3.5") instead of re-explaining.
- When something fails, say what it means in plain words and what the user has to do. Do not paste stack traces.
- Never ask the user to paste a password, token or secret into the chat. They type those into `.env` themselves.

## What needs setting up

There are three independent parts. Only set up what the user wants.

| Part | Needs | Guide section |
|---|---|---|
| Instagram and Facebook (official Meta API) | Instagram professional account linked to a Facebook Page, a Meta app, a Page access token | 3 |
| Followers and DMs to any user (unofficial, instagrapi) | Instagram username and password, one-time login | 4 |
| TikTok posting (official Content Posting API) | TikTok developer app with a saved sandbox, one-time login | 5 |

## Setup order

1. Install: `uv venv --python 3.12`, then `uv pip install -r requirements.txt`. The virtualenv is managed by `uv` and has no `pip`.
2. Settings: `cp env.example .env`, then the user fills in the values (guide section 2).
3. One-time logins, run by the user in a terminal:
   - Instagram: `.venv/bin/python -m src.unofficial_client` (asks for the emailed 6-digit code)
   - TikTok: `.venv/bin/python -m src.tiktok_client` (opens TikTok in the browser, user clicks Authorize)
4. Connect to Claude Code: `claude mcp add --scope user instagram -- /bin/sh -c "cd $HOME/facebook-ig-mcp && exec .venv/bin/python -m src.instagram_mcp_server"`
5. After any code or `.env` change, the user must reconnect with `/mcp`.

## Checking the setup without exposing secrets

Do not `cat`, `grep` or read `.env`, `data/session_*.json` or `data/tiktok_token.json`. Check what is set like this, which prints no values:

```
.venv/bin/python -c "
from src.config import get_settings
s = get_settings()
for k in ('instagram_access_token','facebook_app_id','facebook_app_secret','instagram_business_account_id','instagram_username','instagram_password','tiktok_client_key','tiktok_client_secret'):
    print(k, 'set' if getattr(s, k) else 'EMPTY')
print('tiktok key type:', (s.tiktok_client_key or '')[:2], '(sb = sandbox, aw = production)')
"
```

Then confirm with the read-only tools: `validate_access_token`, `get_profile_info`, `tiktok_get_creator_info`, `get_usage`.

## What the errors mean

| Error | Meaning | What to do |
|---|---|---|
| Settings fail to load at startup | `.env` has a key the code does not know, or a list not written as JSON | Compare with `env.example`. Lists look like `["jpg","png"]` |
| "INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set" | Unofficial tools have no login | User fills both in `.env` |
| "Instagram sent a verification code" | Instagram wants the emailed code | User runs `.venv/bin/python -m src.unofficial_client` |
| Two-factor error on Instagram login | Not supported by this login | Use an account without two-factor |
| Meta token invalid or a permission error | Token expired or a permission was not ticked | Guide step 3.5. The token must be the Page token from `me/accounts` |
| `me/accounts` returns an empty list | The Page was not selected when generating the token | Generate the token again and select the Page |
| TikTok login page says `client_key` | Wrong kind of key, or the app or sandbox was never saved | Use the sandbox keys (`sb...`). Production keys (`aw...`) only work after TikTok approves the app |
| TikTok login page says `redirect_uri` | Login Kit has no saved redirect address | Add `http://localhost:3455/callback/` on the Desktop tab and click Apply changes (step 5.7) |
| `unaudited_client_can_only_post_to_private_accounts` | App is not audited and the TikTok account is public | User sets the TikTok account to private (step 5.1) |
| "Not logged in to TikTok" | No saved TikTok login | User runs `.venv/bin/python -m src.tiktok_client` |
| "Limit reached" | The project's own usage limit | Wait, or check `get_usage` |
| "Already sent a DM to ..." | That user was messaged before | Only resend with `allow_repeat` if the user clearly asks |

TikTok's sandbox does not save until every starred field under Basic information is filled in. Unsaved changes are lost when the tab closes. A target account added to a sandbox can take up to an hour to become active.

## Rules when operating the tools

- **Ask before anything that publishes, sends or deletes**: `publish_media`, `publish_facebook_post`, `tiktok_publish_video`, `tiktok_publish_photos`, `send_dm`, `send_dm_to_user`, `reply_to_comment`, `update_facebook_post`, `delete_facebook_post`, `delete_comment`. Show the exact text and target first.
- **Unofficial tools are risky** (`get_followers`, `send_dm_to_user`). They break Instagram's terms. Tell the user once, keep volume low, never bulk-message, and never send the same text to many people.
- **Respect the limits.** They live in `src/usage.py` and are enforced from the log in `data/usage_<account>.json`. Do not edit that log to get around a limit.
- **TikTok posts default to private** (`SELF_ONLY`). Only use another privacy level when the user asks and `tiktok_get_creator_info` lists it.
- **Keep private data out of git and out of screenshots.** `.env`, `.env.bak` and `data/` are ignored. If you add screenshots to the guide, replace app names, IDs, emails and tokens first.

## Code map

| Path | What it is |
|---|---|
| `src/instagram_mcp_server.py` | MCP server: tool definitions and dispatch |
| `src/instagram_client.py` | Official Meta Graph API client (Instagram and Facebook Page) |
| `src/facebook_tools.py` | Facebook Page and comment tool definitions |
| `src/unofficial_client.py` | Followers and DMs via instagrapi |
| `src/tiktok_client.py` | TikTok login, upload and tool definitions |
| `src/usage.py` | Usage log and limits |
| `src/config.py` | Settings loaded from `.env` |
| `SETUP_GUIDE.md` | User guide. `Instagram_MCP_Setup_Guide.docx` is built from it |
| `docs/images/` | Screenshots used by the guide |

## Working on the code

- Run tests with `.venv/bin/python -m pytest -q`. Two tests in `tests/test_instagram_client.py` (media insights and publish media) fail for reasons unrelated to the tools above.
- Tests mark async functions with `@pytest.mark.asyncio`; `pytest.ini` is not picked up for `asyncio_mode`.
- Adding a tool: define it, map it to a usage action in the server's `OFFICIAL_TOOL_ACTIONS` (or the module's own map), and give that action a limit in `_usage_limits()`.
- After changing `SETUP_GUIDE.md`, rebuild the Word file: `npm install docx`, then `node scripts/build_setup_guide.js SETUP_GUIDE.md Instagram_MCP_Setup_Guide.docx`.
