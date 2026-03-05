from __future__ import annotations

import tempfile
import unittest
from http.cookiejar import Cookie
from pathlib import Path

from cookiekit.cookiestxt import dumps_cookies_txt, load_cookies_txt, load_cookies_txt_lines, save_cookies_txt


def make_cookie(
    *,
    name: str,
    value: str,
    domain: str,
    path: str = "/",
    secure: bool = False,
    expires: int | None = None,
) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=bool(domain),
        domain_initial_dot=domain.startswith("."),
        path=path,
        path_specified=True,
        secure=secure,
        expires=expires,
        discard=expires is None,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


class CookiesTxtTests(unittest.TestCase):
    def test_load_ignores_comments_and_http_only_prefix(self) -> None:
        lines = [
            "# Netscape HTTP Cookie File\n",
            "# a comment\n",
            "#HttpOnly_.example.com\tTRUE\t/\tTRUE\t2147483647\tsessionid\tabc\n",
            "example.com\tFALSE\t/\tFALSE\t0\tcsrftoken\txyz\n",
        ]
        cookies = load_cookies_txt_lines(lines)
        self.assertEqual(len(cookies), 2)
        self.assertEqual(cookies[0].domain, ".example.com")
        self.assertEqual(cookies[0].name, "sessionid")
        self.assertEqual(cookies[1].expires, None)

    def test_load_tolerates_missing_name_field(self) -> None:
        lines = ["example.com\tFALSE\t/\tFALSE\t0\tvalue-only\n"]
        cookies = load_cookies_txt_lines(lines)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0].name, "")
        self.assertEqual(cookies[0].value, "value-only")

    def test_dump_and_save_skip_domainless_cookie(self) -> None:
        cookies = [
            make_cookie(name="a", value="1", domain=".example.com"),
            make_cookie(name="b", value="2", domain=""),
        ]
        text = dumps_cookies_txt(cookies)
        self.assertIn(".example.com", text)
        self.assertNotIn("\tb\t2", text)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cookies.txt"
            save_cookies_txt(path, cookies)
            loaded = load_cookies_txt(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, "a")


if __name__ == "__main__":
    unittest.main()
