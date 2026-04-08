from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "MA" / "capture_topics.py"
SPEC = importlib.util.spec_from_file_location("capture_topics", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
capture_topics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capture_topics
SPEC.loader.exec_module(capture_topics)


def write_file(path: Path, contents: str = "x") -> None:
    path.write_text(contents, encoding="utf-8")


def test_topic_complete_accepts_structural_outputs_from_metadata(tmp_path: Path) -> None:
    topic_dir = tmp_path / "123"
    topic_dir.mkdir()
    write_file(topic_dir / "123.html")
    write_file(topic_dir / "00-TOC.png")
    write_file(topic_dir / "01-structural-1.png")
    write_file(topic_dir / "02-structural-2.png")
    metadata = {
        "topic_id": "123",
        "lesson_count": 2,
        "filenames": ["01-structural-1.png", "02-structural-2.png"],
    }
    (topic_dir / capture_topics.CAPTURE_METADATA_FILE).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    assert capture_topics.topic_complete(topic_dir, "123")


def test_topic_complete_accepts_structural_fallback_from_metadata(tmp_path: Path) -> None:
    topic_dir = tmp_path / "1987"
    topic_dir.mkdir()
    write_file(topic_dir / "1987.html")
    write_file(topic_dir / "00-TOC.png")
    write_file(topic_dir / "01-structural-1.png")
    write_file(topic_dir / "02-structural-2.png")

    metadata = {
        "topic_id": "1987",
        "lesson_count": 2,
        "filenames": ["01-structural-1.png", "02-structural-2.png"],
    }
    (topic_dir / capture_topics.CAPTURE_METADATA_FILE).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    assert capture_topics.topic_complete(topic_dir, "1987")


def test_topic_complete_accepts_existing_structural_fallback_from_state_count(tmp_path: Path) -> None:
    topic_dir = tmp_path / "1989"
    topic_dir.mkdir()
    write_file(topic_dir / "1989.html")
    write_file(topic_dir / "00-TOC.png")
    write_file(topic_dir / "01-structural-1.png")
    write_file(topic_dir / "02-structural-2.png")
    write_file(topic_dir / "03-structural-3.png")

    assert capture_topics.topic_complete(topic_dir, "1989", completed_lesson_count=3)
    assert not capture_topics.topic_complete(topic_dir, "1989", completed_lesson_count=4)
