"""
Setup wizard: collects each key from the user and writes it into the .env file.

For Claude (one value at a time, the normal workflow):
    uv run python -m src.setup_wizard open app-secret      open a window that asks for one value
    uv run python -m src.setup_wizard wait FACEBOOK_APP_SECRET   block until that value is saved
    uv run python -m src.setup_wizard --status             show what is set, without values

For a person doing it alone:
    uv run python -m src.setup_wizard                      ask for everything in turn
    uv run python -m src.setup_wizard ask app-secret       ask for one value in this window

Values that can be asked for: app-id, app-secret, token, instagram-username,
instagram-password, tiktok-key, tiktok-secret.

Secrets are typed with hidden input and are never printed. Run it from the
project folder. It works the same on Mac, Windows and Linux.
"""

import re
import shutil
import subprocess
import sys
import time
from getpass import getpass
from pathlib import Path
from typing import Dict, List, Optional

import httpx

ENV_PATH = Path(".env")
EXAMPLE_PATH = Path("env.example")
GRAPH_URL = "https://graph.facebook.com"

KEYS = {
    "meta": [
        "FACEBOOK_APP_ID",
        "FACEBOOK_APP_SECRET",
        "INSTAGRAM_ACCESS_TOKEN",
        "INSTAGRAM_BUSINESS_ACCOUNT_ID",
    ],
    "instagram": ["INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD"],
    "tiktok": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"],
}

# name -> (env key, hidden input, what it is, where the user finds it)
VALUES = {
    "app-id": (
        "FACEBOOK_APP_ID",
        False,
        "Meta App ID",
        "On the Meta app page: App settings > Basic. It is the number at the top.",
    ),
    "app-secret": (
        "FACEBOOK_APP_SECRET",
        True,
        "Meta App secret",
        "On the Meta app page that is open in your browser: click Show next to "
        "App secret, confirm with your Facebook password, then copy the secret.",
    ),
    "token": (
        "INSTAGRAM_ACCESS_TOKEN",
        True,
        "access token",
        "On the Graph API Explorer page that is open in your browser: click "
        "Generate Access Token, choose your Page and Instagram account, approve, "
        "then click the copy icon to the right of the token.",
    ),
    "instagram-username": (
        "INSTAGRAM_USERNAME",
        False,
        "Instagram username",
        "Your Instagram name, without the @ sign.",
    ),
    "instagram-password": (
        "INSTAGRAM_PASSWORD",
        True,
        "Instagram password",
        "The password you use to log in to Instagram.",
    ),
    "tiktok-key": (
        "TIKTOK_CLIENT_KEY",
        True,
        "TikTok Client key",
        "On the TikTok Sandbox page that is open in your browser: under "
        "Credentials, click the eye icon next to Client key, then copy the key.",
    ),
    "tiktok-secret": (
        "TIKTOK_CLIENT_SECRET",
        True,
        "TikTok Client secret",
        "On the TikTok Sandbox page that is open in your browser: under "
        "Credentials, click the eye icon next to Client secret, then copy it.",
    ),
}


# What each value must look like, so a wrong paste is caught at once
PATTERNS = {
    "FACEBOOK_APP_ID": r"\d{15,17}",
    "FACEBOOK_APP_SECRET": r"[0-9a-f]{32}",
    "INSTAGRAM_ACCESS_TOKEN": r"EA[A-Za-z0-9]{50,}",
    "TIKTOK_CLIENT_KEY": r"[A-Za-z0-9]{12,30}",
    "TIKTOK_CLIENT_SECRET": r"[A-Za-z0-9]{20,64}",
}
EXAMPLE_VALUES = {"123456789012345", "1234567890123456789", "you@example.com"}


def check_value(key: str, value: str):
    """Return (cleaned value, problem). The problem is None when the value looks right."""
    pattern = PATTERNS.get(key)
    if pattern:
        value = "".join(value.split())
        half = value[: len(value) // 2]
        if not re.fullmatch(pattern, value) and half * 2 == value and re.fullmatch(pattern, half):
            value = half  # pasted twice
    if value in EXAMPLE_VALUES:
        return value, "That is the example value from the guide pictures. Use your own."
    if pattern and not re.fullmatch(pattern, value):
        return value, "That does not look right. Copy it again from the page and paste it once."
    return value, None


def meta_app_problem(app_id: str, app_secret: str, version: str = "v19.0") -> Optional[str]:
    """Ask Meta whether the App ID and App secret belong together. None means yes."""
    try:
        reply = httpx.get(
            f"{GRAPH_URL}/{version}/{app_id}",
            params={"fields": "id", "access_token": f"{app_id}|{app_secret}"},
            timeout=30,
        ).json()
    except httpx.HTTPError as error:
        return f"Could not reach Meta to check it: {error}"
    return reply.get("error", {}).get("message") if "error" in reply else None


def read_env() -> Dict[str, str]:
    """Return the KEY=VALUE pairs of the .env file."""
    values: Dict[str, str] = {}
    if ENV_PATH.exists():
        # utf-8-sig also reads files that Notepad on Windows saved with a byte-order mark
        for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def write_values(updates: Dict[str, str]) -> None:
    """Set the given keys in .env, keeping every other line as it is."""
    lines = ENV_PATH.read_text(encoding="utf-8-sig").splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and key in remaining:
            lines[index] = f"{key}={remaining.pop(key)}"
    lines += [f"{key}={value}" for key, value in remaining.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def repair_env() -> None:
    """Fix saved values that were pasted twice. Says which key was fixed, never the value."""
    for key, value in read_env().items():
        if key in PATTERNS and is_set(value):
            cleaned, problem = check_value(key, value)
            if not problem and cleaned != value:
                write_values({key: cleaned})
                print(f"Fixed {key}: it had been pasted twice.")


def ensure_env_file() -> None:
    if not ENV_PATH.exists():
        if not EXAMPLE_PATH.exists():
            raise SystemExit("Run this from the project folder (env.example was not found).")
        shutil.copy(EXAMPLE_PATH, ENV_PATH)
        print("Created the settings file .env from env.example.")


def is_set(value: Optional[str]) -> bool:
    # env.example ships placeholders such as "your_facebook_app_id"
    return bool(value) and not value.startswith("your_")


def print_status() -> None:
    values = read_env()
    for keys in KEYS.values():
        for key in keys:
            value = values.get(key)
            state = "EMPTY" if not is_set(value) else ("LOOKS WRONG" if check_value(key, value)[1] else "set")
            print(f"{key:32} {state}")
    tiktok_key = values.get("TIKTOK_CLIENT_KEY", "")
    if is_set(tiktok_key):
        kind = "sandbox" if tiktok_key.startswith("sb") else "production"
        print(f"TikTok key type: {kind}")


def read_value(prompt: str, secret: bool) -> str:
    value = getpass(prompt) if secret else input(prompt)
    return value.strip().strip("\"'")


def ask(label: str, key: str, secret: bool = False) -> Optional[str]:
    """Prompt for one value. Enter keeps the current one. Returns None when kept."""
    current = read_env().get(key)
    hint = " (press Enter to keep the current value)" if is_set(current) else ""
    for _ in range(3):
        value = read_value(f"{label}{hint}: ", secret)
        if not value:
            return None
        value, problem = check_value(key, value)
        if not problem:
            return value
        print(problem)
    return None


def find_pages(app_id: str, app_secret: str, user_token: str, version: str) -> List[dict]:
    """Extend a user token and return the Pages it manages, with their Page tokens."""
    base = f"{GRAPH_URL}/{version}"
    with httpx.Client(timeout=30) as http:
        extended = http.get(
            f"{base}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": user_token,
            },
        ).json()
        if "access_token" not in extended:
            raise ValueError(extended.get("error", {}).get("message", "Meta refused the token"))
        pages = http.get(
            f"{base}/me/accounts",
            params={
                "fields": "name,access_token,instagram_business_account",
                "access_token": extended["access_token"],
            },
        ).json()
    if "data" not in pages:
        raise ValueError(pages.get("error", {}).get("message", "Meta returned no Pages"))
    return pages["data"]


def save_page_keys(user_token: str, page_name: Optional[str] = None) -> bool:
    """Turn a user token into the Page token and Instagram account number, and save both."""
    values = read_env()
    if not (is_set(values.get("FACEBOOK_APP_ID")) and is_set(values.get("FACEBOOK_APP_SECRET"))):
        print("The App ID and App secret must be saved first.")
        return False
    try:
        pages = find_pages(
            values["FACEBOOK_APP_ID"],
            values["FACEBOOK_APP_SECRET"],
            user_token,
            values.get("INSTAGRAM_API_VERSION") or "v19.0",
        )
    except (ValueError, httpx.HTTPError) as error:
        print(f"Could not get the Page token: {error}")
        return False
    if not pages:
        print("No Pages found. Generate the token again and select your Page in the Facebook window.")
        return False

    wanted = [p for p in pages if page_name and p["name"].lower() == page_name.lower()]
    if wanted:
        page = wanted[0]
    elif len(pages) == 1:
        page = pages[0]
    else:
        if page_name:
            print(f"There is no Page named '{page_name}' in this token.")
        for number, candidate in enumerate(pages, 1):
            linked = "Instagram linked" if candidate.get("instagram_business_account") else "NO Instagram account linked"
            print(f"  {number}. {candidate['name']} ({linked})")
        choice = input(f"Which Page? Type its number [1-{len(pages)}] and press Enter: ").strip() or "1"
        page = pages[int(choice) - 1]

    instagram = page.get("instagram_business_account")
    if not instagram:
        print(f"The Page '{page['name']}' has no Instagram account linked. Link it first, then try again.")
        return False
    write_values(
        {
            "INSTAGRAM_ACCESS_TOKEN": page["access_token"],
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": instagram["id"],
        }
    )
    print(f"Saved the Page token and Instagram account number for '{page['name']}'.")
    return True


def ask_one(name: str, page_name: Optional[str] = None) -> bool:
    """Ask for exactly one value in plain words, save it, and say what to do next."""
    key, secret, title, where = VALUES[name]
    ensure_env_file()
    line = "=" * 64
    print(f"\n{line}\n  Paste here: {title}\n{line}")
    print(f"\nWhere to get it:\n  {where}\n")
    if secret:
        print("Nothing will appear while you paste or type. That is normal.")
    value, problem = "", None
    for _ in range(3):
        value = read_value("Paste it now and press Enter: ", secret)
        if not value:
            break
        value, problem = check_value(key, value)
        if not problem:
            break
        print(problem)

    if not value or problem:
        print("\nNothing was saved, so nothing was changed.")
        saved = False
    elif name == "token":
        saved = save_page_keys(value, page_name)
    else:
        write_values({key: value})
        print(f"\nSaved the {title}.")
        saved = True
        if name == "app-secret":
            current = read_env()
            rejected = meta_app_problem(current.get("FACEBOOK_APP_ID", ""), value, current.get("INSTAGRAM_API_VERSION") or "v19.0")
            if rejected:
                print(f"But Meta does not accept this App ID and App secret together: {rejected}")
                saved = False
            else:
                print("Meta accepted the App ID and App secret.")

    if saved:
        print("You can close this window and go back to Claude.")
    else:
        print("Tell Claude what this window says. Do not copy your keys.")
    return saved


def open_window(name: str, page_name: Optional[str] = None) -> None:
    """Open a new terminal window that asks for one value. Works on Mac, Windows and Linux."""
    folder = str(Path.cwd())
    command = f"uv run python -m src.setup_wizard ask {name}"
    if page_name:
        command += " --page '" + page_name.replace("'", "") + "'"

    if sys.platform == "darwin":
        script = f"cd '{folder}' && {command}".replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e", 'tell application "Terminal" to activate',
             "-e", f'tell application "Terminal" to do script "{script}"'],
            check=True, capture_output=True,
        )
    elif sys.platform == "win32":
        # CREATE_NEW_CONSOLE gives the wizard its own PowerShell window
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command", f"Set-Location -LiteralPath '{folder}'; {command}"],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10),
        )
    else:
        shell_line = f"cd '{folder}' && {command}; echo; read -p 'Press Enter to close' _"
        for terminal in (["x-terminal-emulator", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"], ["xterm", "-e"]):
            if shutil.which(terminal[0]):
                subprocess.Popen(terminal + ["bash", "-lc", shell_line])
                break
        else:
            raise SystemExit(f"No terminal program found. Ask the user to run: {command}")
    print(f"Opened a window asking for the {VALUES[name][2]}.")


def wait_for(key: str, timeout: int = 600) -> bool:
    """Block until the key is saved in .env. Prints the outcome, never the value."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = read_env().get(key)
        if is_set(value) and not check_value(key, value)[1]:
            print(f"{key} set")
            return True
        time.sleep(2)
    print(f"{key} still EMPTY after {timeout} seconds")
    return False


def setup_meta() -> None:
    print("\n--- Facebook and Instagram keys (guide section 3) ---")
    for label, key, secret in (
        ("App ID", "FACEBOOK_APP_ID", False),
        ("App secret", "FACEBOOK_APP_SECRET", True),
    ):
        value = ask(label, key, secret)
        if value:
            write_values({key: value})

    values = read_env()
    if not (is_set(values.get("FACEBOOK_APP_ID")) and is_set(values.get("FACEBOOK_APP_SECRET"))):
        print("App ID and App secret are needed first. Run the wizard again when you have them.")
        return

    print(
        "\nIn the Graph API Explorer, click 'Generate Access Token' and copy the token."
        "\nPaste it here and the wizard finds your Page and saves both Instagram keys."
    )
    user_token = getpass("User access token (press Enter to skip): ").strip()
    if user_token:
        save_page_keys(user_token)


def setup_simple(title: str, fields) -> None:
    print(f"\n--- {title} ---")
    for label, key, secret in fields:
        value = ask(label, key, secret)
        if value:
            write_values({key: value})


def option(arguments: List[str], flag: str) -> Optional[str]:
    return arguments[arguments.index(flag) + 1] if flag in arguments else None


def main(arguments: List[str]) -> None:
    repair_env()
    if "--status" in arguments:
        print_status()
        return

    if arguments and arguments[0] in ("ask", "open", "wait"):
        action, target = arguments[0], (arguments[1] if len(arguments) > 1 else "")
        if action == "wait":
            sys.exit(0 if wait_for(target, int(option(arguments, "--timeout") or 600)) else 1)
        if target not in VALUES:
            raise SystemExit("Choose one of: " + ", ".join(VALUES))
        if action == "open":
            open_window(target, option(arguments, "--page"))
        else:
            ask_one(target, option(arguments, "--page"))
        return

    ensure_env_file()
    parts = [a for a in arguments if a in KEYS] or list(KEYS)
    if "meta" in parts:
        setup_meta()
    if "instagram" in parts:
        setup_simple(
            "Instagram login for followers and messages (guide section 4, optional)",
            (
                ("Instagram username, without @", "INSTAGRAM_USERNAME", False),
                ("Instagram password", "INSTAGRAM_PASSWORD", True),
            ),
        )
    if "tiktok" in parts:
        setup_simple(
            "TikTok keys (guide section 5, optional)",
            (
                ("TikTok Client key", "TIKTOK_CLIENT_KEY", False),
                ("TikTok Client secret", "TIKTOK_CLIENT_SECRET", True),
            ),
        )

    print("\nSaved. What is set now:")
    print_status()
    print(
        "\nNext:"
        "\n  uv run python -m src.unofficial_client   log in to Instagram once (followers and messages)"
        "\n  uv run python -m src.tiktok_client       log in to TikTok once"
        "\n  then reconnect the server in Claude Code with /mcp"
    )


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Nothing else was changed.")
