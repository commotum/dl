from __future__ import annotations

import tempfile
import unittest
from http.cookiejar import Cookie
from pathlib import Path

from cookiekit.cookiestxt import save_cookies_txt
from cookiekit.sources import load_source, parse_source, resolve_update_target


def make_cookie(name: str, domain: str = ".example.com") -> Cookie:
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
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


class SourceTests(unittest.TestCase):
    def test_parse_source(self) -> None:
        file_source = parse_source("cookies.txt")
        self.assertEqual(file_source.kind, "file")

        browser_source = parse_source("browser:firefox/.example.com::Work")
        self.assertEqual(browser_source.kind, "browser")
        self.assertEqual(browser_source.value, "firefox/.example.com::Work")

    def test_load_file_source_and_update_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file = Path(temp_dir) / "cookies.txt"
            save_cookies_txt(cookie_file, [make_cookie("sid")])

            loaded = load_source(parse_source(str(cookie_file)))
            self.assertEqual(len(loaded.cookies), 1)
            self.assertEqual(loaded.update_candidate, str(cookie_file))
            self.assertEqual(resolve_update_target("auto", loaded), str(cookie_file))
            self.assertIsNone(resolve_update_target("off", loaded))

            output_path = str(Path(temp_dir) / "out.txt")
            self.assertEqual(resolve_update_target(output_path, loaded), output_path)

    def test_browser_source_parse_and_not_found(self) -> None:
        source = parse_source("browser:firefox:/definitely/not/a/real/profile/path")
        self.assertEqual(source.kind, "browser")
        with self.assertRaises(FileNotFoundError):
            load_source(source)


if __name__ == "__main__":
    unittest.main()
