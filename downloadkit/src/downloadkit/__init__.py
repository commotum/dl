"""Personal download toolkit."""

from .diagnostics import summarize_result
from .download import DownloadConfig, DownloadError, DownloadResult, fetch
from .validate import DownloadValidationError, detect_file_signature

__all__ = [
    "DownloadConfig",
    "DownloadError",
    "DownloadResult",
    "DownloadValidationError",
    "detect_file_signature",
    "fetch",
    "summarize_result",
]

__version__ = "0.1.0"
