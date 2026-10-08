"""send_dm_to_user falls back to the browser when the instagrapi login fails."""

import pytest

from src import browser_dm, unofficial_client, usage


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "DATA_DIR", tmp_path)
    return tmp_path


def refuse_login(*args, **kwargs):
    raise RuntimeError("Your version of Instagram is out of date.")


def send(**overrides):
    arguments = {
        "login_username": "me",
        "password": "x",
        "message": "hello",
        "username": "friend",
        "user_id": None,
        "daily_limit": 20,
        "allow_repeat": False,
    }
    arguments.update(overrides)
    return unofficial_client._send_dm(**arguments)


def test_login_failure_sends_in_browser_and_logs_it(monkeypatch):
    sent = []
    monkeypatch.setattr(unofficial_client, "_get_client", refuse_login)
    monkeypatch.setattr(
        browser_dm, "send_dm_in_browser", lambda username, message: sent.append((username, message))
    )

    result = send()

    assert sent == [("friend", "hello")]
    assert result["sent_via"] == "browser"
    event = usage.load_events("me")[-1]
    assert (event["action"], event["username"], event["via"]) == ("dm", "friend", "browser")


def test_browser_send_counts_for_the_repeat_guard(monkeypatch):
    monkeypatch.setattr(unofficial_client, "_get_client", refuse_login)
    monkeypatch.setattr(browser_dm, "send_dm_in_browser", lambda username, message: None)
    send()

    with pytest.raises(unofficial_client.RepeatDMError):
        send()


def test_browser_failure_reports_both_errors_and_logs_nothing(monkeypatch):
    def fail(username, message):
        raise browser_dm.BrowserDMError("The browser is not logged in to Instagram.")

    monkeypatch.setattr(unofficial_client, "_get_client", refuse_login)
    monkeypatch.setattr(browser_dm, "send_dm_in_browser", fail)

    with pytest.raises(unofficial_client.UnofficialAPIError) as error:
        send()

    text = str(error.value)
    assert "out of date" in text and "not logged in" in text and "Claude in Chrome" in text
    assert usage.load_events("me") == []


def test_fallback_needs_a_username(monkeypatch):
    monkeypatch.setattr(unofficial_client, "_get_client", refuse_login)

    with pytest.raises(unofficial_client.UnofficialAPIError, match="needs a username"):
        send(username=None, user_id="123")


def test_working_login_does_not_open_the_browser(monkeypatch):
    class Sent:
        id = 7
        thread_id = 9

    class Client:
        def user_id_from_username(self, username):
            return 55

        def direct_send(self, message, user_ids):
            return Sent()

    def no_browser(username, message):
        raise AssertionError("browser must not be used")

    monkeypatch.setattr(unofficial_client, "_get_client", lambda *a, **k: Client())
    monkeypatch.setattr(browser_dm, "send_dm_in_browser", no_browser)

    result = send()

    assert result["sent_via"] == "instagrapi"
    assert result["recipient_user_id"] == "55"
