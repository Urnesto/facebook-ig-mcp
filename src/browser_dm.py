"""
Send an Instagram DM through the instagram.com website with Playwright.

Used by send_dm_to_user as a fallback when the instagrapi login is refused. It
drives a real browser, so Instagram's check on the mobile app version does not
apply. The browser keeps its own profile in data/browser_profile; log in there
once from a terminal:

    uv run python -m src.browser_dm

Passwords are never typed by this module: the user logs in by hand in the window.
"""

from typing import Any, Optional

import structlog

from .usage import DATA_DIR

logger = structlog.get_logger(__name__)

PROFILE_DIR = DATA_DIR / "browser_profile"
INSTAGRAM_URL = "https://www.instagram.com"
LOGIN_COMMAND = "uv run python -m src.browser_dm"
STEP_TIMEOUT_MS = 20_000


class BrowserDMError(Exception):
    """Raised when the browser could not send the message."""


def _open_browser(playwright: Any) -> Any:
    """Open the saved profile in the user's own Chrome or Edge, else Playwright's Chromium."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    last_error: Optional[Exception] = None
    for channel in ("chrome", "msedge", None):
        try:
            return playwright.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                channel=channel,
                headless=False,
                viewport={"width": 1280, "height": 800},
            )
        except Exception as error:  # that browser is not installed; try the next one
            last_error = error
    raise BrowserDMError(
        "No browser could be opened. Install Google Chrome, or run: "
        f"uv run playwright install chromium ({last_error})"
    )


def _start_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise BrowserDMError(
            "Playwright is not installed. Run: uv pip install playwright"
        ) from e
    return sync_playwright()


def _is_logged_in(context: Any) -> bool:
    return any(c["name"] == "sessionid" for c in context.cookies(INSTAGRAM_URL))


def _dismiss_popups(page: Any) -> None:
    """Close the 'Turn on Notifications' prompt if Instagram shows it."""
    button = page.get_by_role("button", name="Not Now")
    try:
        button.first.click(timeout=2_000)
    except Exception:
        pass


def _type_message(page: Any, box: Any, message: str) -> None:
    # Enter sends, so line breaks inside the message go in as Shift+Enter
    box.click()
    for number, line in enumerate(message.split("\n")):
        if number:
            page.keyboard.press("Shift+Enter")
        box.press_sequentially(line, delay=15)


def send_dm_in_browser(username: str, message: str) -> None:
    """Open instagram.com, start a chat with `username` and send `message`."""
    username = username.lstrip("@")
    with _start_playwright() as playwright:
        context = _open_browser(playwright)
        try:
            if not _is_logged_in(context):
                raise BrowserDMError(
                    "The browser is not logged in to Instagram. Log in once from a "
                    f"terminal: {LOGIN_COMMAND}"
                )
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(STEP_TIMEOUT_MS)
            page.goto(f"{INSTAGRAM_URL}/direct/new/", wait_until="domcontentloaded")
            if "/accounts/login" in page.url:
                raise BrowserDMError(
                    "Instagram asked to log in again. Log in once from a "
                    f"terminal: {LOGIN_COMMAND}"
                )
            _dismiss_popups(page)

            dialog = page.get_by_role("dialog")
            search = dialog.locator('input[name="queryBox"]')
            if not search.is_visible():
                page.get_by_role("button", name="Send message").first.click()
            search.click()
            search.press_sequentially(username, delay=40)
            # Results show the username on its own line; the search box holds it as a value
            dialog.get_by_text(username, exact=True).first.click()
            dialog.get_by_role("button", name="Chat").click()

            box = page.locator('div[role="textbox"][contenteditable="true"]').first
            box.wait_for(state="visible")
            _type_message(page, box, message)
            page.keyboard.press("Enter")
            # Instagram empties the box once the message has left it
            page.wait_for_function(
                "box => box.innerText.trim() === ''", arg=box.element_handle()
            )
            page.wait_for_timeout(1_500)
            logger.info("DM sent in the browser", recipient=username)
        except BrowserDMError:
            raise
        except Exception as error:
            raise BrowserDMError(
                f"The browser could not send the message: {str(error).splitlines()[0]}"
            ) from error
        finally:
            context.close()


def login(timeout_seconds: int = 300) -> bool:
    """Open the browser on Instagram's login page and wait for the user to log in."""
    with _start_playwright() as playwright:
        context = _open_browser(playwright)
        try:
            if _is_logged_in(context):
                return True
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(f"{INSTAGRAM_URL}/accounts/login/", wait_until="domcontentloaded")
            for _ in range(timeout_seconds):
                if _is_logged_in(context):
                    page.wait_for_timeout(3_000)  # let Instagram finish saving the login
                    return True
                page.wait_for_timeout(1_000)
            return False
        finally:
            context.close()


if __name__ == "__main__":
    print("A browser window opens. Log in to Instagram there; this window waits.")
    if login():
        print(f"Logged in. The browser profile is saved in {PROFILE_DIR}")
    else:
        raise SystemExit("No login after 5 minutes. Run the command again.")
