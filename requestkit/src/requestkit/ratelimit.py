"""Rate-limit helpers for requestkit."""

from __future__ import annotations

import time
from collections.abc import Callable


def sleep(seconds: float, reason: str | None = None, *, sleeper: Callable[[float], None] = time.sleep) -> float:
    """Sleep for a non-negative number of seconds and return the applied delay."""

    del reason
    delay = max(0.0, float(seconds))
    if delay:
        sleeper(delay)
    return delay


def wait(
    *,
    seconds: float | None = None,
    until: float | None = None,
    adjust: float = 0.0,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
) -> float:
    """Wait until a timestamp or for a number of seconds."""

    if seconds is None and until is None:
        raise ValueError("Either 'seconds' or 'until' is required")

    if seconds is None:
        seconds = float(until) - clock()

    return sleep(float(seconds) + adjust, sleeper=sleeper)
