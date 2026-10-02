"""
Unit tests for the setup wizard that writes the .env file.
"""

from unittest.mock import MagicMock, patch

import pytest

from src import setup_wizard


@pytest.fixture
def env_file(tmp_path):
    """Point the wizard at a scratch .env file."""
    path = tmp_path / ".env"
    with patch.object(setup_wizard, "ENV_PATH", path):
        yield path


class TestEnvFile:
    def test_write_values_replaces_and_appends_without_touching_other_lines(self, env_file):
        env_file.write_text("# Instagram\nFACEBOOK_APP_ID=your_facebook_app_id\nLOG_LEVEL=INFO\n")

        setup_wizard.write_values({"FACEBOOK_APP_ID": "123", "TIKTOK_CLIENT_KEY": "sbabc"})

        assert env_file.read_text() == (
            "# Instagram\nFACEBOOK_APP_ID=123\nLOG_LEVEL=INFO\nTIKTOK_CLIENT_KEY=sbabc\n"
        )

    def test_placeholders_and_blanks_count_as_empty(self, env_file):
        env_file.write_text("FACEBOOK_APP_ID=your_facebook_app_id\nFACEBOOK_APP_SECRET=\nINSTAGRAM_USERNAME=me\n")

        values = setup_wizard.read_env()

        assert not setup_wizard.is_set(values["FACEBOOK_APP_ID"])
        assert not setup_wizard.is_set(values["FACEBOOK_APP_SECRET"])
        assert setup_wizard.is_set(values["INSTAGRAM_USERNAME"])

    def test_status_never_prints_values(self, env_file, capsys):
        env_file.write_text("FACEBOOK_APP_SECRET=topsecret\nTIKTOK_CLIENT_KEY=sbkey123\n")

        setup_wizard.print_status()

        out = capsys.readouterr().out
        assert "topsecret" not in out and "sbkey123" not in out
        assert "FACEBOOK_APP_SECRET" in out and "TikTok key type: sandbox" in out


class TestMetaSetup:
    def _http(self, *responses):
        http = MagicMock()
        http.get.side_effect = [MagicMock(json=MagicMock(return_value=r)) for r in responses]
        http.__enter__.return_value = http
        return http

    def test_find_pages_extends_the_token_then_lists_pages(self):
        http = self._http(
            {"access_token": "long_user_token"},
            {"data": [{"name": "My Page", "access_token": "page_token"}]},
        )

        with patch.object(setup_wizard.httpx, "Client", return_value=http):
            pages = setup_wizard.find_pages("app", "secret", "short_token", "v19.0")

        exchange, accounts = http.get.call_args_list
        assert exchange.kwargs["params"]["fb_exchange_token"] == "short_token"
        assert accounts.kwargs["params"]["access_token"] == "long_user_token"
        assert pages == [{"name": "My Page", "access_token": "page_token"}]

    def test_find_pages_reports_metas_error_message(self):
        http = self._http({"error": {"message": "Invalid OAuth access token."}})

        with patch.object(setup_wizard.httpx, "Client", return_value=http):
            with pytest.raises(ValueError, match="Invalid OAuth access token"):
                setup_wizard.find_pages("app", "secret", "bad", "v19.0")

    def test_setup_meta_saves_page_token_and_instagram_id(self, env_file):
        env_file.write_text("FACEBOOK_APP_ID=123\nFACEBOOK_APP_SECRET=abc\nINSTAGRAM_ACCESS_TOKEN=\n")
        pages = [
            {"name": "My Page", "access_token": "page_token", "instagram_business_account": {"id": "178"}}
        ]

        with patch.object(setup_wizard, "getpass", side_effect=["", "user_token"]), patch(
            "builtins.input", side_effect=[""]
        ), patch.object(setup_wizard, "find_pages", return_value=pages):
            setup_wizard.setup_meta()

        values = setup_wizard.read_env()
        assert values["INSTAGRAM_ACCESS_TOKEN"] == "page_token"
        assert values["INSTAGRAM_BUSINESS_ACCOUNT_ID"] == "178"
        assert values["FACEBOOK_APP_SECRET"] == "abc"


class TestAskOne:
    """The one-value windows Claude opens for the user."""

    def test_ask_one_saves_a_secret_without_printing_it(self, env_file, capsys):
        env_file.write_text("FACEBOOK_APP_SECRET=\n")

        secret = "0123456789abcdef0123456789abcde0"
        with patch.object(setup_wizard, "getpass", return_value=secret), patch.object(
            setup_wizard, "meta_app_problem", return_value=None
        ):
            assert setup_wizard.ask_one("app-secret") is True

        assert setup_wizard.read_env()["FACEBOOK_APP_SECRET"] == secret
        out = capsys.readouterr().out
        assert secret not in out and "go back to Claude" in out

    def test_a_secret_pasted_twice_is_saved_once(self, env_file):
        secret = "0123456789abcdef0123456789abcde0"
        with patch.object(setup_wizard, "getpass", return_value=secret + secret), patch.object(
            setup_wizard, "meta_app_problem", return_value=None
        ):
            assert setup_wizard.ask_one("app-secret") is True

        assert setup_wizard.read_env()["FACEBOOK_APP_SECRET"] == secret

    def test_the_example_app_id_from_the_guide_is_refused(self, env_file, capsys):
        env_file.write_text("FACEBOOK_APP_ID=1234567890123456\n")

        with patch("builtins.input", return_value="123456789012345"):
            assert setup_wizard.ask_one("app-id") is False

        assert setup_wizard.read_env()["FACEBOOK_APP_ID"] == "1234567890123456"
        assert "example value" in capsys.readouterr().out

    def test_a_secret_meta_rejects_is_reported(self, env_file, capsys):
        with patch.object(setup_wizard, "getpass", return_value="0123456789abcdef0123456789abcde0"), patch.object(
            setup_wizard, "meta_app_problem", return_value="Invalid Client ID"
        ):
            assert setup_wizard.ask_one("app-secret") is False

        assert "Invalid Client ID" in capsys.readouterr().out

    def test_ask_one_with_nothing_entered_changes_nothing(self, env_file, capsys):
        env_file.write_text("TIKTOK_CLIENT_SECRET=old\n")

        with patch.object(setup_wizard, "getpass", return_value=""):
            assert setup_wizard.ask_one("tiktok-secret") is False

        assert setup_wizard.read_env()["TIKTOK_CLIENT_SECRET"] == "old"
        assert "nothing was changed" in capsys.readouterr().out

    def test_token_picks_the_named_page_without_asking(self, env_file):
        env_file.write_text("FACEBOOK_APP_ID=123\nFACEBOOK_APP_SECRET=abc\n")
        pages = [
            {"name": "Old Page", "access_token": "old_token", "instagram_business_account": {"id": "1"}},
            {"name": "Test test", "access_token": "new_token", "instagram_business_account": {"id": "2"}},
        ]

        with patch.object(setup_wizard, "getpass", return_value="EA" + "x" * 60), patch.object(
            setup_wizard, "find_pages", return_value=pages
        ), patch("builtins.input", side_effect=AssertionError("should not ask")):
            assert setup_wizard.ask_one("token", page_name="test test") is True

        values = setup_wizard.read_env()
        assert values["INSTAGRAM_ACCESS_TOKEN"] == "new_token"
        assert values["INSTAGRAM_BUSINESS_ACCOUNT_ID"] == "2"

    def test_token_for_a_page_without_instagram_is_refused(self, env_file, capsys):
        env_file.write_text("FACEBOOK_APP_ID=123\nFACEBOOK_APP_SECRET=abc\n")
        pages = [{"name": "Test test", "access_token": "t"}]

        with patch.object(setup_wizard, "getpass", return_value="EA" + "x" * 60), patch.object(
            setup_wizard, "find_pages", return_value=pages
        ):
            assert setup_wizard.ask_one("token") is False

        assert "INSTAGRAM_ACCESS_TOKEN" not in setup_wizard.read_env()
        assert "no Instagram account linked" in capsys.readouterr().out

    def test_wait_for_returns_once_the_key_is_saved(self, env_file):
        env_file.write_text("FACEBOOK_APP_SECRET=0123456789abcdef0123456789abcde0\nINSTAGRAM_PASSWORD=\n")

        assert setup_wizard.wait_for("FACEBOOK_APP_SECRET", timeout=1) is True
        with patch.object(setup_wizard.time, "sleep"):
            assert setup_wizard.wait_for("INSTAGRAM_PASSWORD", timeout=0) is False


class TestOpenWindow:
    """The command that opens a one-value window on each operating system."""

    def test_windows_opens_powershell_in_a_new_console(self):
        with patch.object(setup_wizard.sys, "platform", "win32"), patch.object(
            setup_wizard.subprocess, "Popen"
        ) as popen, patch.object(setup_wizard.Path, "cwd", return_value=setup_wizard.Path("C:/Users/me/facebook-ig-mcp")):
            setup_wizard.open_window("token", "Test two")

        arguments = popen.call_args.args[0]
        assert arguments[:3] == ["powershell", "-NoExit", "-Command"]
        assert "uv run python -m src.setup_wizard ask token --page 'Test two'" in arguments[3]
        assert "facebook-ig-mcp" in arguments[3]
        assert popen.call_args.kwargs["creationflags"] == 0x10

    def test_mac_opens_terminal(self):
        with patch.object(setup_wizard.sys, "platform", "darwin"), patch.object(
            setup_wizard.subprocess, "run"
        ) as run:
            setup_wizard.open_window("app-secret")

        arguments = run.call_args.args[0]
        assert arguments[0] == "osascript"
        assert "uv run python -m src.setup_wizard ask app-secret" in arguments[-1]

    def test_linux_uses_the_first_terminal_it_finds(self):
        with patch.object(setup_wizard.sys, "platform", "linux"), patch.object(
            setup_wizard.shutil, "which", side_effect=lambda name: "/usr/bin/xterm" if name == "xterm" else None
        ), patch.object(setup_wizard.subprocess, "Popen") as popen:
            setup_wizard.open_window("tiktok-key")

        arguments = popen.call_args.args[0]
        assert arguments[:2] == ["xterm", "-e"]
        assert "ask tiktok-key" in arguments[-1]

    def test_env_file_saved_by_notepad_with_a_byte_order_mark_is_read(self, env_file):
        env_file.write_bytes(b"\xef\xbb\xbfFACEBOOK_APP_ID=1234567890123456\r\nLOG_LEVEL=INFO\r\n")

        assert setup_wizard.read_env()["FACEBOOK_APP_ID"] == "1234567890123456"
        setup_wizard.write_values({"LOG_LEVEL": "DEBUG"})
        assert setup_wizard.read_env() == {"FACEBOOK_APP_ID": "1234567890123456", "LOG_LEVEL": "DEBUG"}
