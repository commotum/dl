"""Validation helpers for downloadkit."""

from __future__ import annotations

from pathlib import Path

from requests import Response


class DownloadValidationError(RuntimeError):
    """Raised when a response does not look like the expected file."""


SIGNATURES = {
    "jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    "webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    "pdf": lambda data: data.startswith(b"%PDF-"),
    "zip": lambda data: data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")),
    "mp4": lambda data: len(data) >= 12 and data[4:8] == b"ftyp",
}


def detect_file_signature(data: bytes) -> str | None:
    for name, matcher in SIGNATURES.items():
        if matcher(data):
            return name
    return None


def validate_response_metadata(
    response: Response,
    output: str | Path,
    *,
    expected_content_type: str | tuple[str, ...] | None = None,
    html_is_error: bool = True,
) -> None:
    content_type = (response.headers.get("Content-Type") or "").lower()
    suffix = Path(output).suffix.lower()

    if expected_content_type:
        expected = (
            (expected_content_type,)
            if isinstance(expected_content_type, str)
            else expected_content_type
        )
        if not any(value.lower() in content_type for value in expected):
            raise DownloadValidationError(
                f"Unexpected content type {response.headers.get('Content-Type')!r}"
            )

    if html_is_error and "text/html" in content_type and suffix not in {".html", ".htm"}:
        raise DownloadValidationError("Received HTML where a binary download was expected")


def validate_file_signature(
    output: str | Path,
    data: bytes,
    *,
    validate_signature: bool = True,
) -> None:
    if not validate_signature or not data:
        return

    suffix = Path(output).suffix.lower().lstrip(".")
    if not suffix or suffix not in SIGNATURES:
        return

    actual = detect_file_signature(data)
    if actual is None:
        return
    if actual != suffix and not (suffix == "jpg" and actual == "jpeg"):
        raise DownloadValidationError(
            f"File signature {actual!r} does not match output extension {suffix!r}"
        )
