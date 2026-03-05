from __future__ import annotations

from cookiekit import save_cookies_txt
from requests.cookies import create_cookie

from requestkit import RequestClient, SessionConfig, build_session


def test_build_session_applies_browser_preset_and_referer():
    session = build_session(
        SessionConfig(browser="chrome", referer="https://example.com/")
    )

    assert "Chrome/138.0.0.0" in session.headers["User-Agent"]
    assert session.headers["Referer"] == "https://example.com/"
    assert "sec-ch-ua" in session.headers


def test_request_client_retries_server_errors(http_server):
    client = RequestClient(SessionConfig(retries=1))
    text = client.request_text(http_server["base_url"] + "/retry")

    assert text == "retried ok\n"
    assert http_server["state"]["retry"] == 2


def test_request_client_retries_429(http_server):
    client = RequestClient(SessionConfig(retries=1, sleep_429=0.0))
    text = client.request_text(http_server["base_url"] + "/429")

    assert text == "rate limit recovered\n"
    assert http_server["state"]["429"] == 2


def test_request_client_loads_cookies_txt(http_server, tmp_path):
    cookie_path = tmp_path / "cookies.txt"
    save_cookies_txt(
        cookie_path,
        [create_cookie(name="sessionid", value="abc123", domain="127.0.0.1", path="/")],
    )

    client = RequestClient(SessionConfig(cookies=cookie_path))
    payload = client.request_json(http_server["base_url"] + "/cookie")

    assert payload["cookie"] == "sessionid=abc123"
