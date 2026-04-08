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


def test_selectable_course_count_ignores_placeholder_and_disabled_options() -> None:
    payload = {
        "selected": "",
        "options": [
            {"value": "", "label": "-", "disabled": False, "group": ""},
            {"value": "113", "label": "Mathematical Foundations I", "disabled": False, "group": "Mathematical Foundations"},
            {"value": "111", "label": "Mathematical Foundations II", "disabled": True, "group": "Mathematical Foundations"},
        ],
    }

    assert capture_courses.selectable_course_count(payload) == 1


def test_wait_for_selected_course_passes_payload_as_keyword_arg() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def wait_for_function(self, expression: str, **kwargs: object) -> None:
            self.calls.append((expression, kwargs))

    page = FakePage()

    capture_courses.wait_for_selected_course(page, "Mathematical Foundations II", 12345)

    assert len(page.calls) == 1
    expression, kwargs = page.calls[0]
    assert "courseName" in expression
    assert kwargs == {
        "arg": {
            "selector": capture_courses.CURRENT_COURSE_SELECTOR,
            "courseName": "Mathematical Foundations II",
        },
        "timeout": 12345,
    }


def test_wait_for_save_actionable_waits_for_overlay_and_enabled_button() -> None:
    class FakeCollection:
        def __init__(self, page: "FakePage") -> None:
            self.page = page

        def evaluate_all(self, _expression: str) -> bool:
            return self.page.cover_states[self.page.cover_index]

    class FakePage:
        def __init__(self) -> None:
            self.url = "https://mathacademy.com/settings/course"
            self.cover_states = [True, False]
            self.cover_index = 0
            self.wait_calls = 0

        def locator(self, selector: str) -> FakeCollection:
            assert selector == capture_courses.SCREEN_COVER_SELECTOR
            return FakeCollection(self)

        def wait_for_timeout(self, _ms: int) -> None:
            self.wait_calls += 1
            if self.cover_index < len(self.cover_states) - 1:
                self.cover_index += 1

    class FakeSaveButton:
        def __init__(self) -> None:
            self.disabled_states = [True, False]
            self.disabled_index = 0

        def evaluate(self, _expression: str) -> bool:
            value = self.disabled_states[self.disabled_index]
            if self.disabled_index < len(self.disabled_states) - 1:
                self.disabled_index += 1
            return value

        def is_visible(self) -> bool:
            return True

    page = FakePage()
    save_button = FakeSaveButton()

    course = capture_courses.CourseRecord("143", "SAT Math Prep", "Test Prep")

    capture_courses.wait_for_save_actionable(
        page,
        save_button,
        1000,
        baseline_screen_covers=0,
        course=course,
    )

    assert page.wait_calls >= 1


def test_course_complete_accepts_html_and_matching_metadata(tmp_path: Path) -> None:
    course_dir = tmp_path / "111"
    course_dir.mkdir()
    write_file(course_dir / "111.html")
    (course_dir / capture_courses.COURSE_METADATA_FILE).write_text(
        json.dumps({"course_id": "111", "name": "Mathematical Foundations II"}),
        encoding="utf-8",
    )

    assert capture_courses.course_complete(course_dir, "111")
