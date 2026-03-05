"""Source selection helpers."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Sequence, TypeVar

from .persist import atomic_write_text

T = TypeVar("T")


def select_source(
    sources: Sequence[T],
    *,
    mode: str = "first",
    rotate_index: int = 0,
    rng: random.Random | None = None,
) -> tuple[T, int]:
    """Select a source and return (selected_source, next_rotate_index)."""
    if not sources:
        raise ValueError("no sources provided")

    if mode == "first":
        return sources[0], rotate_index

    if mode == "random":
        chooser = rng if rng is not None else random
        return chooser.choice(list(sources)), rotate_index

    if mode == "rotate":
        index = int(rotate_index) % len(sources)
        return sources[index], rotate_index + 1

    raise ValueError(f"unsupported selection mode: {mode!r}")


def load_rotate_index(path: str | Path) -> int:
    state_path = Path(path)
    if not state_path.exists():
        return 0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    index = data.get("rotate_index", 0)
    try:
        return int(index)
    except (TypeError, ValueError):
        return 0


def save_rotate_index(path: str | Path, rotate_index: int) -> None:
    payload = {"rotate_index": int(rotate_index)}
    atomic_write_text(path, json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
