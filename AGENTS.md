# Instructions for AI agents

Full reference: [CLAUDE.md](CLAUDE.md). Step-by-step setup: the `setup-social-mcp` skill in [.claude/skills/setup-social-mcp/SKILL.md](.claude/skills/setup-social-mcp/SKILL.md). User guide with screenshots: [SETUP_GUIDE.md](SETUP_GUIDE.md).

## Your job

Do the whole setup for the user and collect every value yourself, except the secrets listed below. The user is usually not technical: never hand them a list of steps to work through alone.

## What you collect and do yourself

- Install: `uv venv --python 3.12`, `uv pip install -r requirements.txt`.
- Check what is filled in: `uv run python -m src.setup_wizard --status` (prints `set` or `EMPTY`, never a value).
- Open every web page the setup needs, fill in forms with the details the user gave (Page name, category, app name, website, terms and privacy addresses, redirect address), and click through the screens.
- Read non-secret identifiers from those pages and write them into `.env` yourself:
  - Meta App ID → `FACEBOOK_APP_ID`
  - Instagram username → `INSTAGRAM_USERNAME`
  - `uv run python -c "from src import setup_wizard as w; w.write_values({'KEY': 'VALUE'})"`
- Verify each part with the read-only tools and report what works.

## The workflow for secrets

The user does not know how to do this, so Claude handles everything around the secrets. For each one:

1. **Navigate** to the page where the secret is shown and point out the button to click.
2. **Open a window** for that one value: `uv run python -m src.setup_wizard open NAME`
3. **Tell the user one sentence:** click, copy, paste into the window, press Enter.
4. **Wait** until it is saved: `uv run python -m src.setup_wizard wait KEY`
5. **Carry on.** Never reveal, copy, type or ask for the secret yourself.

| Secret | Page Claude opens | `open NAME` | `wait KEY` |
|---|---|---|---|
| Meta App secret | Meta app → App settings → Basic (user clicks Show) | `app-secret` | `FACEBOOK_APP_SECRET` |
| Access token | Graph API Explorer (user clicks Generate Access Token, then the copy icon) | `token --page "PAGE NAME"` | `INSTAGRAM_ACCESS_TOKEN` |
| Instagram password | none | `instagram-password` | `INSTAGRAM_PASSWORD` |
| TikTok Client key | TikTok app → Sandbox → Credentials (user clicks the eye icon) | `tiktok-key` | `TIKTOK_CLIENT_KEY` |
| TikTok Client secret | same page | `tiktok-secret` | `TIKTOK_CLIENT_SECRET` |

The `token` window turns the Explorer token into `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_BUSINESS_ACCOUNT_ID` on its own.

The user also does these themselves: logging in, approval screens ("Generate Access Token", "Authorize", "Add account"), and security codes sent by SMS or email.

## Commands

Every command must work on Mac, Windows and Linux. Use `uv run python -m ...`; never `.venv/bin/...` or shell-specific syntax.
