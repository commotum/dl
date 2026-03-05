"""Path helpers for downloadkit."""

from __future__ import annotations

from pathlib import Path


def ensure_parent(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def part_path_for(output: str | Path) -> Path:
    target = Path(output)
    return target.with_name(f".{target.name}.part")


def remove_if_exists(path: str | Path) -> None:
    target = Path(path)
    try:
        target.unlink()
    except FileNotFoundError:
        return
