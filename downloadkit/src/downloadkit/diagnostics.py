"""Diagnostics helpers for downloadkit."""

from __future__ import annotations

from .download import DownloadResult


def summarize_result(result: DownloadResult) -> dict[str, object]:
    return {
        "status": result.status,
        "source_url": result.source_url,
        "used_url": result.used_url,
        "final_url": result.final_url,
        "output": str(result.output),
        "bytes_written": result.bytes_written,
        "attempts": result.attempts,
        "resumed": result.resumed,
        "used_fallback": result.used_fallback,
        "content_type": result.content_type,
    }
