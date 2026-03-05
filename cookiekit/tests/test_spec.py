from __future__ import annotations

import unittest

from cookiekit.spec import parse_browser_spec


class SpecTests(unittest.TestCase):
    def test_parse_minimal(self) -> None:
        spec = parse_browser_spec("firefox")
        self.assertEqual(spec.browser, "firefox")
        self.assertIsNone(spec.profile)
        self.assertIsNone(spec.keyring)
        self.assertIsNone(spec.container)
        self.assertIsNone(spec.domain)

    def test_parse_full(self) -> None:
        spec = parse_browser_spec("chrome/.example.com+kwallet:Default::Work")
        self.assertEqual(spec.browser, "chrome")
        self.assertEqual(spec.domain, ".example.com")
        self.assertEqual(spec.keyring, "kwallet")
        self.assertEqual(spec.profile, "Default")
        self.assertEqual(spec.container, "Work")

    def test_invalid_browser(self) -> None:
        with self.assertRaises(ValueError):
            parse_browser_spec("unknown-browser")


if __name__ == "__main__":
    unittest.main()
