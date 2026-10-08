"""Check whether aiograpi can log in to Instagram with the saved settings.

Read-only: it logs in and reads the account's own username. It sends nothing,
and it works on a copy of the saved session, so data/ is left untouched.

usage: uv run python scripts/test_aiograpi_login.py
"""

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from aiograpi import Client  # noqa: E402

from src.config import get_settings  # noqa: E402


async def main() -> int:
    settings = get_settings()
    if not settings.instagram_username or not settings.instagram_password:
        print("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD are not set in .env")
        return 1

    client = Client()
    saved = PROJECT / "data" / f"session_{settings.instagram_username}.json"
    with tempfile.TemporaryDirectory() as folder:
        if saved.exists():
            copy = Path(folder) / saved.name
            shutil.copy(saved, copy)
            try:
                client.load_settings(copy)
            except Exception as error:  # an instagrapi session aiograpi cannot read
                print(f"Saved session not used: {type(error).__name__}")
        try:
            await client.login(settings.instagram_username, settings.instagram_password)
            account = await client.account_info()
        except Exception as error:
            print(f"LOGIN FAILED: {type(error).__name__}: {str(error)[:300]}")
            return 1

    version = client.get_settings().get("device_settings", {}).get("app_version")
    print(f"LOGIN OK as {account.username} (app version {version})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
