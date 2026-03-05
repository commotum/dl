"""Diagnostics helpers for requestkit."""

from __future__ import annotations

from collections.abc import Mapping

from requests import Response

from .challenge import detect_challenge

REDACTED = "<redacted>"
SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}
TEXTUAL_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/xhtml+xml",
)


def redact_header_value(name: str, value: str) -> str:
    if name.strip().lower() in SENSITIVE_HEADERS:
        return REDACTED
    return value


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {name: redact_header_value(name, value) for name, value in headers.items()}


def is_textual_content_type(content_type: str | None) -> bool:
    if not content_type:
        return True
    lowered = content_type.lower()
    return lowered.startswith(TEXTUAL_CONTENT_TYPES) or "+json" in lowered or "+xml" in lowered


def _decode_payload(payload: bytes | str | None, encoding: str | None = None) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload

    for candidate in (encoding, "utf-8", "latin-1"):
        if not candidate:
            continue
        try:
            return payload.decode(candidate)
        except UnicodeDecodeError:
            continue

    return payload.decode("utf-8", errors="replace")


def body_preview(response: Response, max_body_bytes: int | None = 16_384) -> str:
    content = response.content
    if max_body_bytes is not None:
        content = content[:max_body_bytes]

    if not is_textual_content_type(response.headers.get("Content-Type")):
        return f"<{len(response.content)} bytes binary>"

    return _decode_payload(content, response.encoding or response.apparent_encoding)


def summarize_response(
    response: Response,
    *,
    include_body: bool = False,
    max_body_bytes: int | None = 16_384,
) -> dict[str, object]:
    request = response.request
    summary: dict[str, object] = {
        "method": request.method,
        "request_url": request.url,
        "url": response.url,
        "status_code": response.status_code,
        "reason": response.reason,
        "ok": response.ok,
        "challenge": detect_challenge(response),
        "content_type": response.headers.get("Content-Type"),
        "request_headers": redact_headers(request.headers),
        "response_headers": redact_headers(response.headers),
    }

    if request.body:
        summary["request_body"] = _decode_payload(request.body)

    if include_body:
        summary["body"] = body_preview(response, max_body_bytes=max_body_bytes)

    return summary


def format_exchange(
    response: Response,
    *,
    include_body: bool = True,
    max_body_bytes: int | None = 16_384,
) -> str:
    request = response.request
    request_headers = redact_headers(request.headers)
    response_headers = redact_headers(response.headers)

    lines = [
        f"{request.method} {request.url}",
        f"Status: {response.status_code} {response.reason}",
    ]

    challenge = detect_challenge(response)
    if challenge:
        lines.append(f"Challenge: {challenge}")

    lines.extend(
        [
            "",
            "Request Headers",
            "---------------",
        ]
    )
    lines.extend(f"{name}: {value}" for name, value in request_headers.items())

    if request.body:
        lines.extend(
            [
                "",
                "Request Body",
                "------------",
                _decode_payload(request.body),
            ]
        )

    lines.extend(
        [
            "",
            "Response Headers",
            "----------------",
        ]
    )
    lines.extend(f"{name}: {value}" for name, value in response_headers.items())

    if include_body:
        lines.extend(
            [
                "",
                "Response Body",
                "-------------",
                body_preview(response, max_body_bytes=max_body_bytes),
            ]
        )

    return "\n".join(lines) + "\n"
