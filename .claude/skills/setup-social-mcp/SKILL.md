---
name: setup-social-mcp
description: Set up this Instagram, Facebook and TikTok MCP server for the user from start to finish - install, create the Facebook Page and Meta app, collect the keys, fill in .env through the setup wizard, run the one-time logins, connect the server and verify it. Use when the user asks to set up, install, configure, connect or fix this project, or says a tool is not working because of missing keys or logins.
---

# Set up the Instagram, Facebook and TikTok MCP server

Do the whole setup for the user. They are usually not technical. Do every step you can yourself, and when a step needs them, tell them exactly one thing to do and wait.

This file contains every step. `SETUP_GUIDE.md` has the same steps with a screenshot for every click; point the user to its step numbers when they need to see a screen.

## Ground rules

**Commands.** Every command works the same on Mac, Windows and Linux. Run them from the project folder. Use `uv run python -m ...`; never `.venv/bin/...` or shell-specific syntax.

**Who does what.**

| Claude does | The user does |
|---|---|
| Installs, runs checks, reads `--status`, opens the window for each secret | Copies each secret and drops it into the window Claude opened |
| Navigates to every page, including the pages where secrets are shown | Logs in to Facebook, Instagram and TikTok |
| Fills in forms with non-secret values the user has agreed to (Page name, app name, website, redirect address) | Clicks approval screens: "Generate Access Token", "Authorize", "Add account" |
| Writes non-secret identifiers into `.env` (Meta App ID, Instagram username) | Completes security checks: SMS codes, emailed codes, "was this you" prompts |
| Verifies with read-only tools and explains errors | Decides what gets published, sent or deleted |

**Secrets.** These are secret: Meta App secret, any access token, Instagram password, TikTok Client key and Client secret.

- A value still in square brackets in the user's prompt (for example `[my_instagram_name]` or `[yes / no]`) was not filled in. Ask for it when its step comes up; do not guess.
- Never ask for a secret in the chat, never type one into a form or file, and never click a "Show" or eye icon that reveals one.
- Never read, print, `cat` or `grep` `.env`, `data/session_*.json` or `data/tiktok_token.json`.
- If the user pastes a secret into the chat, do not repeat it. Tell them to enter it in the wizard and to regenerate it if it was a token or app secret.
- If the user asks Claude to collect or enter the secrets, say plainly that this is the one part Claude cannot do, and open the page where the value is shown so they only copy and paste.

**The secret hand-off.** The user does not know how to do any of this. Claude does every action; the user's only job is to copy a value and drop it into a small window. For each secret, do exactly this:

1. **Navigate.** Open the page where the secret is shown (browser extension if available, otherwise give the link). Scroll to it and point out the button: **Show**, the eye icon, or **Generate Access Token**.
2. **Open the window.** Run `uv run python -m src.setup_wizard open NAME`. It opens a new terminal window on Mac, Windows or Linux that asks for that one value, says in plain words where it is, and hides what is pasted.
3. **Say one sentence.** For example: "Click Show, copy the secret, paste it into the window that just opened, and press Enter."
4. **Wait.** Run `uv run python -m src.setup_wizard wait KEY`. It returns as soon as the value is saved, or after 10 minutes. Do not ask the user to confirm; the command tells you.
5. **Continue** with the next step. If the wait times out, ask what the window says.

| NAME | KEY to wait for | Page to open first |
|---|---|---|
| `app-secret` | `FACEBOOK_APP_SECRET` | Meta app → App settings → Basic |
| `token --page "PAGE NAME"` | `INSTAGRAM_ACCESS_TOKEN` | Graph API Explorer, app and permissions already selected |
| `instagram-password` | `INSTAGRAM_PASSWORD` | none |
| `tiktok-key` | `TIKTOK_CLIENT_KEY` | TikTok app → Sandbox → Credentials |
| `tiktok-secret` | `TIKTOK_CLIENT_SECRET` | same page |

The `token` window turns the Explorer token into the Page token and the Instagram account number and saves both; with `--page` it picks the Page by name and asks nothing else.

`uv run python -m src.setup_wizard --status` prints `set` or `EMPTY` per key and the TikTok key type, never a value. `uv run python -m src.setup_wizard` with no arguments asks for everything in one window; use it only if the user prefers that.

**Ask before changing anything public or lasting.** Creating a Page or an app, saving app settings and adding products all need a clear yes from the user, with the values you will enter listed first.

## Step 1. Install

1. Run `uv --version`. If `uv` is missing, give the user the line for their system and wait:
   - Mac or Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. If there is no `.venv` folder, run `uv venv --python 3.12`.
3. Run `uv pip install -r requirements.txt`.

## Step 2. See what is missing

1. Run `uv run python -m src.setup_wizard --status`.
2. Ask which parts the user wants: Facebook and Instagram (official), followers and direct messages (unofficial), TikTok.
3. Check the browser. If the browser tools are available, open https://developers.facebook.com/apps/ and see whether the user is logged in. If a login page appears, ask the user to log in (Facebook, Instagram, TikTok, and the two developer sites) and wait; never log in for them. If the browser tools are not available, tell the user to install the Claude in Chrome extension from https://claude.com/chrome and start Claude with `claude --chrome`; without it, give links and instructions and let the user click.
4. Do not open any window yet. Each secret gets its own window at the moment it is needed (see "The secret hand-off").

## Step 3. Facebook Page

Skip if the user already has the Page they want to use.

1. Open https://www.facebook.com/pages/create
2. Type the **Page name** and choose a **Category** from the suggestions. Ask the user for both first.
3. Click **Create Page**.
4. If Facebook shows "We noticed suspicious activity: Finish SMS verification on mobile app", stop. The user completes the verification in the Facebook app on their phone, then clicks **Create Page** themselves.

## Step 4. Link the Instagram account to the Page

The Instagram account must be a Business or Creator account. An Instagram account can be linked to only one Page at a time; ask before moving it from another Page.

1. On Facebook, the user clicks their profile photo, then **See all profiles**, and selects the Page.
2. Click the Page's profile picture, then **Settings & privacy → Settings**.
3. Under **Permissions**, click **Linked accounts**.
4. Click **Instagram**, then **Connect account**. The user logs in to Instagram.

Shortcut: right after creating a Page, Facebook is already switched into it, so https://www.facebook.com/settings/?tab=linked_instagram opens the Instagram screen directly. Open it and let the user click **Connect account**.

After **Create Page**, Facebook shows five optional "Finish setting up your Page" screens. Click **Next** or **Skip** through them without adding contact details, WhatsApp or invitations, switch off the marketing emails toggle on the last one, and click **Done**.

Help page: https://www.facebook.com/help/1148909221857370

## Step 5. Meta app

Skip to step 6 if the user already has a Meta app.

1. Open https://developers.facebook.com/apps/creation/ (the user registers as a developer if asked).
2. **App details:** type an app name. Click **Next**.
3. **Use cases:** click the **Content management** filter, tick **Manage messaging & content on Instagram** and **Manage everything on your Page**. Click **Next**.
4. **Business:** select **I don't want to connect a business portfolio yet**. Click **Next**.
5. **Requirements:** click **Next**.
6. **Overview:** click **Create app**. Facebook may ask the user for their password.
7. Leave the app in **Development** mode.

## Step 6. Facebook keys: App ID and App secret

1. Open https://developers.facebook.com/apps/ and click the app, then **App settings → Basic**.
2. The **App ID** is an identifier, not a secret. Claude may write it to `.env`:
   `uv run python -c "from src import setup_wizard as w; w.write_values({'FACEBOOK_APP_ID': 'THE_ID'})"`
3. Hand-off for `app-secret`: the page is already open, so run `open app-secret`, tell the user to click **Show**, confirm with their Facebook password, copy the secret and paste it into the window, then run `wait FACEBOOK_APP_SECRET`.

## Step 7. Instagram keys: access token and account number

1. Open https://developers.facebook.com/tools/explorer/
2. Under **Meta App**, pick the app.
3. In the **User or Page** dropdown, choose **Get User Access Token**.
4. Under **Permissions**, open the dropdown below **Add a Permission** and tick:
   `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`, `pages_manage_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `instagram_manage_comments`, `read_insights`, `business_management`, and `instagram_manage_messages` plus `pages_manage_metadata` only if the user wants to read and reply to DMs (the two go together; DMs also need **Allow access to messages** switched on in the Instagram app under Connected tools).
5. The user clicks **Generate Access Token**, selects their **Page** and **Instagram account** in the Facebook window, and approves.
6. Hand-off for `token`: run `open token --page "PAGE NAME"`, tell the user to click the copy icon next to the token and paste it into the window, then run `wait INSTAGRAM_ACCESS_TOKEN`. The window extends the token and saves the Page token and the Instagram account number.
7. Run `--status`. All four Meta values should be `set`.

Manual route, if the wizard cannot reach Meta: click the **ⓘ** icon next to the token, **Open in Access Token Tool**, **Extend Access Token**; paste the extended token back into the Explorer; submit `me/accounts?fields=name,access_token,instagram_business_account`; the Page's `access_token` and the `id` inside `instagram_business_account` are the two values.

## Step 8. Followers and direct messages (optional, unofficial)

Tell the user once: this logs in like the phone app, breaks Instagram's terms, and can get an account restricted, so a spare account is safer. Accounts with two-factor authentication cannot log in this way.

1. Write the username yourself (`w.write_values({'INSTAGRAM_USERNAME': 'name'})`), then do the hand-off for `instagram-password` and `wait INSTAGRAM_PASSWORD`.
2. The user runs `uv run python -m src.unofficial_client` in a terminal and types the 6-digit code Instagram emails.
3. When it prints **Logged in as**, the session is saved in `data/`.

## Step 9. TikTok (optional)

1. **TikTok account.** It must be set to private until TikTok has audited the app: in the TikTok app, **Profile → Menu → Settings and privacy → Privacy → Private account**.
2. **Developer account.** The user signs up or logs in at https://developers.tiktok.com/signup
3. **App.** At https://developers.tiktok.com/apps/ click **Connect an app**, select **Individual**, **Confirm**.
4. **Sandbox.** On the app page click **Sandbox**, then **Create Sandbox**, type a name, **Confirm**.
5. **Basic information.** All starred fields are required or nothing saves: App icon (1024 x 1024 JPG or PNG), App name, Category, Description, Terms of Service URL, Privacy Policy URL. Ask the user for these values.
6. **Platforms.** Tick **Desktop** and fill in **Web/Desktop URL** with the user's website.
7. **Products.** Click **Add products**, add **Login Kit** first, then **Content Posting API**, then **Done**.
8. **Redirect address.** In the Login Kit box, click the **Desktop** tab and enter `http://localhost:3455/callback/`
9. **Direct Post.** In the Content Posting API box, switch on **Direct Post**. The scopes `user.info.basic`, `video.publish` and `video.upload` appear on their own.
10. **Save.** Click **Apply changes** and wait for "Saved". If it reports errors, click **Review** and fill in what is missing.
11. **Target user.** Under **Sandbox settings → Target Users**, click **Add account**, then **Continue**. The user logs in with their TikTok account. It can take up to an hour to become active.
12. **Keys.** With the **Sandbox** page open at **Credentials**, do the hand-off twice: `open tiktok-key` then `wait TIKTOK_CLIENT_KEY`, and `open tiktok-secret` then `wait TIKTOK_CLIENT_SECRET`. The user clicks the eye icon each time. `--status` must show key type `sandbox`.
13. **Login.** The user runs `uv run python -m src.tiktok_client` and clicks **Authorize** in the browser.

To post publicly later: on the app page click **Production → Import**, choose the sandbox, fill in **App review**, click **Submit for review**. After approval, the Production keys replace the sandbox ones and the login is repeated.

## Step 10. Connect and verify

1. The server is defined in `.mcp.json`. The user starts `claude` in the project folder and approves the **instagram** server, or types `/mcp` and reconnects it. After any `.env` change or new login they must reconnect.
2. Run `uv run python -m src.setup_wizard --status` once more.
3. Verify each part with a read-only tool: `validate_access_token` and `get_profile_info` (Meta), `get_facebook_posts` (Page), `get_followers` (unofficial login), `tiktok_get_creator_info` (TikTok), `get_usage`.
4. Tell the user plainly what works and what is still missing.

## When something fails

| What you see | Meaning | What to do |
|---|---|---|
| Facebook: "Finish SMS verification on mobile app" | Account security check | User completes it in the Facebook phone app |
| Settings fail to load | Unknown key in `.env`, or a list not written as JSON | Compare with `env.example` |
| `me/accounts` returns no Pages | The Page was not selected when the token was generated | Step 7 again, selecting the Page |
| No Instagram account on the Page | Not linked, or not a Business or Creator account | Step 4 |
| Meta permission error | A permission was not ticked | Step 7 again |
| "Instagram sent a verification code" | Instagram wants the emailed code | User runs `uv run python -m src.unofficial_client` |
| TikTok login page says `client_key` | Production key of an unapproved app, or nothing saved | Use the sandbox keys; check step 9.10 |
| TikTok login page says `redirect_uri` | Redirect address not saved | Step 9.8 and 9.10 |
| `unaudited_client_can_only_post_to_private_accounts` | TikTok account is public | Step 9.1 |
| "Not logged in to TikTok" | No saved login | Step 9.13 |
| "Limit reached" or "Already sent a DM to" | The project's own safety limits | Check `get_usage`; do not work around them |

## Do not

- Do not publish, send a message or delete anything as a "test" without asking first. Verify with the read-only tools.
- Do not log in, approve permission screens, or solve verification prompts for the user.
- Do not work around a security check or a refusal from Facebook, Instagram or TikTok.
- Do not edit `data/usage_*.json` to get around a limit.
