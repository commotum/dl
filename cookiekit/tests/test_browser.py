from __future__ import annotations

import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cookiekit.browser import load_browser_cookies, parse_webkit_binarycookies
from cookiekit.spec import BrowserSpec


def create_firefox_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE moz_cookies (
                name TEXT,
                value TEXT,
                host TEXT,
                path TEXT,
                isSecure INTEGER,
                expiry INTEGER,
                originAttributes TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sid", "no-container", "example.com", "/", 0, 2000000000, ""),
        )
        conn.execute(
            "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sid", "container", "example.com", "/", 0, 2000000000, "userContextId=2"),
        )
        conn.execute(
            "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sid", "subdomain", "sub.example.com", "/", 0, 2000000000, ""),
        )
        conn.commit()
    finally:
        conn.close()


def create_chromium_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE cookies (
                host_key TEXT,
                name TEXT,
                value TEXT,
                encrypted_value BLOB,
                path TEXT,
                expires_utc INTEGER,
                is_secure INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("example.com", "plain", "abc", b"", "/", 13253760000000000, 0),
        )
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("example.com", "enc", "", b"v10encrypted", "/", 13253760000000000, 1),
        )
        conn.commit()
    finally:
        conn.close()


def build_webkit_blob() -> bytes:
    domain = b"example.com\x00"
    name = b"sid\x00"
    path = b"/\x00"
    value = b"abc\x00"

    base_header_size = 56
    domain_offset = base_header_size
    name_offset = domain_offset + len(domain)
    path_offset = name_offset + len(name)
    value_offset = path_offset + len(path)
    payload = domain + name + path + value
    record_size = base_header_size + len(payload)

    record = b"".join(
        [
            struct.pack("<I", record_size),  # size
            struct.pack("<I", 0),  # unknown
            struct.pack("<I", 1),  # secure flag
            struct.pack("<I", 0),  # unknown
            struct.pack("<I", domain_offset),
            struct.pack("<I", name_offset),
            struct.pack("<I", path_offset),
            struct.pack("<I", value_offset),
            b"\x00" * 8,
            struct.pack("<d", 1000.0),  # expiration (mac absolute)
            struct.pack("<d", 0.0),  # creation
            payload,
        ]
    )

    page = b"".join(
        [
            b"\x00\x00\x01\x00",
            struct.pack("<I", 1),
            struct.pack("<I", 16),
            b"\x00" * 4,
            record,
        ]
    )
    return b"cook" + struct.pack(">I", 1) + struct.pack(">I", len(page)) + page


class BrowserTests(unittest.TestCase):
    def test_firefox_domain_and_container_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "default-release"
            profile_dir.mkdir(parents=True)
            db = profile_dir / "cookies.sqlite"
            create_firefox_db(db)

            (profile_dir / "containers.json").write_text(
                json.dumps(
                    {
                        "identities": [
                            {"name": "Work", "userContextId": 2, "l10nID": "userContext2.label"}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            none_spec = BrowserSpec(
                browser="firefox",
                profile=str(profile_dir),
                domain="example.com",
                container="none",
            )
            none = load_browser_cookies(none_spec)
            self.assertEqual({cookie.value for cookie in none}, {"no-container"})

            all_spec = BrowserSpec(
                browser="firefox",
                profile=str(profile_dir),
                domain=".example.com",
                container="all",
            )
            all_cookies = load_browser_cookies(all_spec)
            self.assertEqual(
                {cookie.value for cookie in all_cookies},
                {"no-container", "container", "subdomain"},
            )

            container_spec = BrowserSpec(
                browser="firefox",
                profile=str(profile_dir),
                domain="example.com",
                container="Work",
            )
            only_container = load_browser_cookies(container_spec)
            self.assertEqual({cookie.value for cookie in only_container}, {"container"})

    def test_chromium_domain_filter_and_encrypted_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "Default"
            profile_dir.mkdir(parents=True)
            db = profile_dir / "Cookies"
            create_chromium_db(db)

            spec = BrowserSpec(browser="chrome", profile=str(profile_dir), domain="example.com")
            cookies = load_browser_cookies(spec)

            self.assertEqual(len(cookies), 1)
            self.assertEqual(cookies[0].name, "plain")
            # Chromium epoch conversion should produce a unix timestamp.
            self.assertEqual(cookies[0].expires, 1609286400)

    def test_sqlite_fallback_to_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "Default"
            profile_dir.mkdir(parents=True)
            db = profile_dir / "Cookies"
            create_chromium_db(db)

            original_connect = sqlite3.connect

            def flaky_connect(*args, **kwargs):
                if kwargs.get("uri"):
                    raise sqlite3.OperationalError("immutable open failed")
                return original_connect(*args, **kwargs)

            spec = BrowserSpec(browser="chrome", profile=str(profile_dir), domain="example.com")
            with mock.patch("cookiekit.browser.sqlite3.connect", side_effect=flaky_connect):
                cookies = load_browser_cookies(spec)

            self.assertEqual(len(cookies), 1)
            self.assertEqual(cookies[0].name, "plain")

    def test_webkit_binarycookies_parser(self) -> None:
        blob = build_webkit_blob()
        cookies = parse_webkit_binarycookies(blob, domain="example.com")
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0].name, "sid")
        self.assertEqual(cookies[0].value, "abc")


if __name__ == "__main__":
    unittest.main()
