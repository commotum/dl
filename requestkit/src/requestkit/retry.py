"""Retry helpers for requestkit."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class RetryPolicy:
    """Minimal retry policy for request/session operations."""

    retries: int = 4
    retry_statuses: tuple[int, ...] = field(default_factory=tuple)
    retry_429: bool = True
    retry_5xx: bool = True
    backoff_factor: float = 1.0


def should_retry_status(status_code: int, policy: RetryPolicy) -> bool:
    if status_code == 429:
        return policy.retry_429
    if status_code in policy.retry_statuses:
        return True
    if 500 <= status_code < 600:
        return policy.retry_5xx
    return False


def retry_delay(attempt: int, policy: RetryPolicy) -> float:
    attempt = max(1, int(attempt))
    return float(policy.backoff_factor) * attempt
