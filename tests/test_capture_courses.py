from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "MA" / "capture_courses.py"
SPEC = importlib.util.spec_from_file_location("capture_courses", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
capture_courses = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capture_courses
SPEC.loader.exec_module(capture_courses)


def write_file(path: Path, contents: str = "x") -> None:
    path.write_text(contents, encoding="utf-8")


def test_parse_args_restores_course_111_by_default() -> None:
    args = capture_courses.parse_args(["--dry-run"])

    assert args.restore_original_course is True
    assert args.restore_course_id == "111"


def test_course_records_from_dialog_state_reads_selected_and_groups() -> None:
    selected, courses = capture_courses.course_records_from_dialog_state(
        {
            "selected": "111",
            "options": [
                {"value": "113", "label": "Mathematical Foundations I", "disabled": False, "group": "Mathematical Foundations"},
                {"value": "111", "label": "Mathematical Foundations II", "disabled": False, "group": "Mathematical Foundations"},
                {"value": "111", "label": "Duplicate", "disabled": False, "group": "Ignored"},
                {"value": "999", "label": "Disabled", "disabled": True, "group": "Ignored"},
            ],
        }
    )

    assert selected == "111"
    assert courses == [
        capture_courses.CourseRecord("113", "Mathematical Foundations I", "Mathematical Foundations"),
        capture_courses.CourseRecord("111", "Mathematical Foundations II", "Mathematical Foundations"),
    ]


def test_course_complete_accepts_html_and_matching_metadata(tmp_path: Path) -> None:
    course_dir = tmp_path / "111"
    course_dir.mkdir()
    write_file(course_dir / "111.html")
    (course_dir / capture_courses.COURSE_METADATA_FILE).write_text(
        json.dumps({"course_id": "111", "name": "Mathematical Foundations II"}),
        encoding="utf-8",
    )

    assert capture_courses.course_complete(course_dir, "111")
