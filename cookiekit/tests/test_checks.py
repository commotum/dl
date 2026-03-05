from __future__ import annotations

import unittest
from datetime import datetime, timezone
from http.cookiejar import Cookie

from cookiekit.checks import check_required_cookies


def make_cookie(name: str, domain: str, expires: int | None) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value="value",
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=domain.startswith("."),
        path="/",
        path_specified=True,
        secure=False,
        expires=expires,
        discard=expires is None,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


class CheckTests(unittest.TestCase):
    def test_missing_cookie(self) -> None:
        result = check_required_cookies([], ["sessionid"])
        self.assertFalse(result.ok)
        self.assertEqual(result.missing, ("sessionid",))

    def test_expired_and_expiring_soon(self) -> None:
        now = int(datetime.now(tz=timezone.utc).timestamp())
        cookies = [
            make_cookie("expired", ".example.com", now - 10),
            make_cookie("soon", ".example.com", now + 30),
            make_cookie("good", ".example.com", now + 100000),
        ]
        result = check_required_cookies(
            cookies,
            ["expired", "soon", "good"],
            domain="example.com",
            allow_subdomains=True,
            expiring_soon_seconds=60,
            now=now,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.expired, ("expired",))
        self.assertEqual(result.expiring_soon, ("soon",))

    def test_domain_filtered_match(self) -> None:
        now = int(datetime.now(tz=timezone.utc).timestamp())
        cookies = [make_cookie("sid", ".sub.example.com", now + 100)]

        strict = check_required_cookies(
            cookies,
            ["sid"],
            domain="example.com",
            allow_subdomains=False,
            now=now,
        )
        self.assertEqual(strict.missing, ("sid",))

        relaxed = check_required_cookies(
            cookies,
            ["sid"],
            domain="example.com",
            allow_subdomains=True,
            now=now,
        )
        self.assertTrue(relaxed.ok)


if __name__ == "__main__":
    unittest.main()
