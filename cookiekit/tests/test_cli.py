from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cookiekit.cli import main
from cookiekit.cookiestxt import load_cookies_txt, save_cookies_txt
from http.cookiejar import Cookie


def make_cookie(name: str, value: str, domain: str) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
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


class CliTests(unittest.TestCase):
    def test_load_and_check_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file = Path(temp_dir) / "cookies.txt"
            save_cookies_txt(cookie_file, [make_cookie("sid", "1", ".example.com")])

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc_load = main(["load", str(cookie_file)])
            self.assertEqual(rc_load, 0)
            self.assertIn("Loaded 1 cookies", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc_check = main(
                    [
                        "check",
                        str(cookie_file),
                        "--require",
                        "sid",
                        "--domain",
                        "example.com",
                        "--allow-subdomains",
                    ]
                )
            self.assertEqual(rc_check, 0)
            self.assertIn("OK", stdout.getvalue())

    def test_parse_spec_command(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(["parse-spec", "firefox/.example.com::Work"])
        self.assertEqual(rc, 0)
        self.assertIn('"browser": "firefox"', stdout.getvalue())
        self.assertIn('"container": "Work"', stdout.getvalue())

    def test_sync_rotate_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_a = Path(temp_dir) / "a.txt"
            source_b = Path(temp_dir) / "b.txt"
            state = Path(temp_dir) / "rotate.json"
            save_cookies_txt(source_a, [make_cookie("a", "1", ".example.com")])
            save_cookies_txt(source_b, [make_cookie("b", "1", ".example.com")])

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc1 = main(
                    [
                        "sync",
                        "--source",
                        str(source_a),
                        "--source",
                        str(source_b),
                        "--select",
                        "rotate",
                        "--rotate-state-file",
                        str(state),
                        "--cookies-update",
                        "off",
                    ]
                )
            self.assertEqual(rc1, 0)
            self.assertIn(f"Selected source: file:{source_a}", stdout.getvalue())

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc2 = main(
                    [
                        "sync",
                        "--source",
                        str(source_a),
                        "--source",
                        str(source_b),
                        "--select",
                        "rotate",
                        "--rotate-state-file",
                        str(state),
                        "--cookies-update",
                        "off",
                    ]
                )
            self.assertEqual(rc2, 0)
            self.assertIn(f"Selected source: file:{source_b}", stdout.getvalue())

    def test_noop_alias_and_explicit_update_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.txt"
            output = Path(temp_dir) / "out.txt"
            save_cookies_txt(source, [make_cookie("sid", "1", ".example.com")])

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "noop",
                        "--source",
                        str(source),
                        "--cookies-update",
                        str(output),
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertIn(f"Updated cookies at: {output}", stdout.getvalue())
            self.assertEqual(len(load_cookies_txt(output)), 1)

    def test_sync_browser_source_failure_message(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(
                [
                    "sync",
                    "--source",
                    "browser:firefox:/definitely/not/a/real/profile/path",
                ]
            )
        self.assertEqual(rc, 2)
        self.assertIn("Source error:", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
