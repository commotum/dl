"""Resume helpers for downloadkit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import part_path_for


@dataclass(slots=True, frozen=True)
class ResumeState:
    part_path: Path
    offset: int
    use_range: bool
    mode: str
    resumed: bool


def build_resume_state(output: str | Path, *, resume: bool) -> ResumeState:
    part_path = part_path_for(output)

    if resume and part_path.exists():
        offset = part_path.stat().st_size
        if offset > 0:
            return ResumeState(
                part_path=part_path,
                offset=offset,
                use_range=True,
                mode="ab",
                resumed=True,
            )

    return ResumeState(
        part_path=part_path,
        offset=0,
        use_range=False,
        mode="wb",
        resumed=False,
    )
