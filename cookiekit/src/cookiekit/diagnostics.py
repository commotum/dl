"""Diagnostics helpers with secret redaction."""

from __future__ import annotations

from collections.abc import Mapping

REDACTED = "<redacted>"
SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}


def redact_header_value(name: str, value: str) -> str:
    if name.strip().lower() in SENSITIVE_HEADERS:
        return REDACTED
    return value


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for name, value in headers.items():
        redacted[name] = redact_header_value(name, value)
    return redacted


def redact_http_header_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    for line in lines:
        if ":" not in line:
            result.append(line)
            continue
        name, value = line.split(":", 1)
        safe_value = redact_header_value(name, value.strip())
        result.append(f"{name}: {safe_value}")
    return result
