from __future__ import annotations

import json

from cookiekit import save_cookies_txt
from requests.cookies import create_cookie

from requestkit.cli import main


def test_cli_get_json_outputs_body(http_server, capsys):
    exit_code = main(["get", http_server["base_url"] + "/json", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status_code"] == 200
    assert '"ok": true' in payload["body"]


def test_cli_dump_redacts_cookie_header(http_server, tmp_path, capsys):
    cookie_path = tmp_path / "cookies.txt"
    save_cookies_txt(
        cookie_path,
        [create_cookie(name="sessionid", value="secret-value", domain="127.0.0.1", path="/")],
    )

    exit_code = main(["dump", http_server["base_url"] + "/text", "--cookies", str(cookie_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Cookie: <redacted>" in captured.out
    assert "secret-value" not in captured.out
