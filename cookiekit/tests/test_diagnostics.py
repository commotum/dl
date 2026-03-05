from __future__ import annotations

import unittest

from cookiekit.diagnostics import REDACTED, redact_header_value, redact_headers, redact_http_header_lines


class DiagnosticsTests(unittest.TestCase):
    def test_redact_header_value(self) -> None:
        self.assertEqual(redact_header_value("Authorization", "Bearer abc"), REDACTED)
        self.assertEqual(redact_header_value("Cookie", "a=1"), REDACTED)
        self.assertEqual(redact_header_value("Set-Cookie", "a=1"), REDACTED)
        self.assertEqual(redact_header_value("User-Agent", "UA"), "UA")

    def test_redact_headers_mapping(self) -> None:
        headers = {
            "Authorization": "Bearer abc",
            "Cookie": "sid=1",
            "User-Agent": "ua",
        }
        redacted = redact_headers(headers)
        self.assertEqual(redacted["Authorization"], REDACTED)
        self.assertEqual(redacted["Cookie"], REDACTED)
        self.assertEqual(redacted["User-Agent"], "ua")

    def test_redact_http_header_lines(self) -> None:
        lines = [
            "GET / HTTP/1.1",
            "Authorization: Bearer abc",
            "Cookie: sid=1",
            "User-Agent: ua",
        ]
        redacted = redact_http_header_lines(lines)
        self.assertEqual(redacted[0], "GET / HTTP/1.1")
        self.assertEqual(redacted[1], f"Authorization: {REDACTED}")
        self.assertEqual(redacted[2], f"Cookie: {REDACTED}")
        self.assertEqual(redacted[3], "User-Agent: ua")


if __name__ == "__main__":
    unittest.main()
