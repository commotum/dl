"""Personal request/session toolkit."""

from .challenge import detect_challenge
from .diagnostics import format_exchange, redact_header_value, redact_headers, summarize_response
from .retry import RetryPolicy
from .session import RequestClient, ResponseValidationError, SessionConfig, build_session

__all__ = [
    "RequestClient",
    "ResponseValidationError",
    "RetryPolicy",
    "SessionConfig",
    "build_session",
    "detect_challenge",
    "format_exchange",
    "redact_header_value",
    "redact_headers",
    "summarize_response",
]

__version__ = "0.1.0"
