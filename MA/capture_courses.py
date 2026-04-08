#!/usr/bin/env python3
"""Capture hydrated Math Academy course progress pages by iterating course settings."""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cookiekit import load_browser_cookies, load_cookies_txt, parse_browser_spec
from playwright.sync_api import (
    BrowserContext,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "course-progress"
DEFAULT_STATE_FILE = "_course_progress_state.jsonl"
COURSE_METADATA_FILE = "_course_meta.json"
DEFAULT_SETTINGS_URL = "https://mathacademy.com/settings/course"
DEFAULT_PROGRESS_URL_TEMPLATE = "https://mathacademy.com/courses/{course_id}/progress"
CONFIGURE_BUTTON_SELECTOR = "#configureCourseButton"
CURRENT_COURSE_SELECTOR = "#course"
COURSE_DIALOG_SELECTOR = "#configureCourseDialog-course, #courseDialog-course"
COURSE_SELECT_SELECTOR = "#configureCourseDialog-courseSelect, #courseDialog-courseSelect"
BUTTON_BAR_SELECTOR = "#configureCourseDialog-buttonBar, #courseDialog-buttonBar"
SAVE_BUTTON_SELECTOR = "#configureCourseDialog-saveButton, #courseDialog-saveButton"
CANCEL_BUTTON_SELECTOR = "#configureCourseDialog-cancelButton, #courseDialog-cancelButton"


@dataclass(frozen=True)
class CourseRecord:
    course_id: str
    name: str
    group: str | None = None


class CaptureError(RuntimeError):
    """Base class for course-capture failures."""


class RetryableCaptureError(CaptureError):
    """Temporary failure that can be retried after backing off."""


class AuthenticationRequiredError(CaptureError):
    """Raised when the page looks unauthenticated or blocked."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture hydrated Math Academy course progress HTML by iterating course settings.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where per-course capture folders will be created.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Optional JSONL state log path. Defaults to OUTPUT_ROOT/_course_progress_state.jsonl.",
    )
    parser.add_argument(
        "--settings-url",
        default=DEFAULT_SETTINGS_URL,
        help="Course settings page used to open the configure-course dialog.",
    )
    parser.add_argument(
        "--progress-url-template",
        default=DEFAULT_PROGRESS_URL_TEMPLATE,
        help="Format string for per-course progress pages. Must include {course_id}.",
    )

    auth = parser.add_argument_group("authentication")
    auth.add_argument(
        "--browser-spec",
        help=(
            "Browser cookie source in cookiekit format, e.g. "
            "'chrome/.mathacademy.com:Default' or 'firefox/.mathacademy.com::Personal'."
        ),
    )
    auth.add_argument(
        "--cookies",
        type=Path,
        help="Existing cookies.txt file to load instead of reading from a browser profile.",
    )
    auth.add_argument(
        "--cookie-domain",
        dest="cookie_domains",
        action="append",
        default=None,
        help=(
            "Cookie domain suffix to keep. Repeatable. "
            "Defaults to '.mathacademy.com'."
        ),
    )

    selection = parser.add_argument_group("selection")
    selection.add_argument(
        "--course-id",
        dest="course_ids",
        action="append",
        default=[],
        help="Specific course ID to capture. Repeatable.",
    )
    selection.add_argument(
        "--start-at",
        help="Start processing at this course ID within the dialog order.",
    )
    selection.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of courses to process after filtering.",
    )
    selection.add_argument(
        "--force",
        action="store_true",
        help="Recapture courses even if output files already look complete.",
    )
    selection.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print what would run without opening the browser.",
    )
    selection.add_argument(
        "--restore-original-course",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Restore --restore-course-id after the batch completes.",
    )
    selection.add_argument(
        "--restore-course-id",
        default="111",
        help="Course ID to restore after the batch completes. Defaults to 111.",
    )

    browser = parser.add_argument_group("playwright")
    browser.add_argument(
        "--engine",
        choices=("chromium", "firefox", "webkit"),
        default="chromium",
        help="Playwright browser engine to use.",
    )
    browser.add_argument(
        "--headed",
        action="store_true",
        help="Run a visible browser window instead of headless mode.",
    )
    browser.add_argument(
        "--viewport-width",
        type=int,
        default=1440,
        help="Viewport width.",
    )
    browser.add_argument(
        "--viewport-height",
        type=int,
        default=2200,
        help="Viewport height.",
    )
    browser.add_argument(
        "--device-scale-factor",
        type=float,
        default=1.0,
        help="Playwright device scale factor.",
    )
    browser.add_argument(
        "--timeout-ms",
        type=int,
        default=45_000,
        help="Per-operation timeout in milliseconds.",
    )
    browser.add_argument(
        "--settle-wait-ms",
        type=int,
        default=500,
        help="Small wait after navigation or dialog changes before reading the DOM.",
    )

    pacing = parser.add_argument_group("pacing")
    pacing.add_argument(
        "--sleep-course-min",
        type=float,
        default=10.0,
        help="Minimum seconds to sleep between courses.",
    )
    pacing.add_argument(
        "--sleep-course-max",
        type=float,
        default=25.0,
        help="Maximum seconds to sleep between courses.",
    )
    pacing.add_argument(
        "--rest-every",
        type=int,
        default=20,
        help="Take a longer rest after every N successfully captured courses. Set 0 to disable.",
    )
    pacing.add_argument(
        "--rest-min",
        type=float,
        default=120.0,
        help="Minimum seconds for longer periodic rests.",
    )
    pacing.add_argument(
        "--rest-max",
        type=float,
        default=360.0,
        help="Maximum seconds for longer periodic rests.",
    )
    pacing.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Number of retries for transient course-level failures.",
    )
    pacing.add_argument(
        "--retry-base-seconds",
        type=float,
        default=30.0,
        help="Base backoff seconds for transient course-level failures.",
    )
    pacing.add_argument(
        "--retry-max-seconds",
        type=float,
        default=180.0,
        help="Maximum retry backoff seconds.",
    )

    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the batch on the first non-authentication capture failure.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Console log level.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the interactive tqdm progress bar.",
    )

    args = parser.parse_args(argv)
    validate_args(args)
    return args


def validate_args(args: argparse.Namespace) -> None:
    for low_name, high_name in (
        ("sleep_course_min", "sleep_course_max"),
        ("rest_min", "rest_max"),
    ):
        low = getattr(args, low_name)
        high = getattr(args, high_name)
        if high < low:
            raise SystemExit(f"{high_name.replace('_', '-')} must be >= {low_name.replace('_', '-')}")

    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    if args.rest_every is not None and args.rest_every < 0:
        raise SystemExit("--rest-every cannot be negative")
    if args.retries < 0:
        raise SystemExit("--retries cannot be negative")
    if args.device_scale_factor <= 0:
        raise SystemExit("--device-scale-factor must be positive")
    if args.timeout_ms <= 0:
        raise SystemExit("--timeout-ms must be positive")
    if args.settle_wait_ms < 0:
        raise SystemExit("--settle-wait-ms cannot be negative")
    if "{course_id}" not in args.progress_url_template:
        raise SystemExit("--progress-url-template must include {course_id}")
    args.restore_course_id = str(args.restore_course_id).strip()
    if args.restore_original_course and not args.restore_course_id:
        raise SystemExit("--restore-course-id cannot be empty when restoration is enabled")

    if args.cookie_domains is None:
        args.cookie_domains = [".mathacademy.com"]

    if args.dry_run:
        return

    if bool(args.browser_spec) == bool(args.cookies):
        raise SystemExit("Provide exactly one of --browser-spec or --cookies")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def course_sort_key(course_id: str) -> tuple[int, int | str]:
    return (0, int(course_id)) if course_id.isdigit() else (1, course_id)


def progress_url(course_id: str, args: argparse.Namespace) -> str:
    return args.progress_url_template.format(course_id=course_id)


def select_courses(courses: list[CourseRecord], args: argparse.Namespace) -> list[CourseRecord]:
    selected = courses

    if args.course_ids:
        wanted = {value.strip() for value in args.course_ids}
        selected = [course for course in selected if course.course_id in wanted]

    if args.start_at:
        start_index = next(
            (index for index, course in enumerate(selected) if course.course_id == args.start_at),
            None,
        )
        if start_index is None:
            raise SystemExit(f"--start-at course {args.start_at!r} was not found after filtering")
        selected = selected[start_index:]

    if args.limit is not None:
        selected = selected[: args.limit]

    return selected


def nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def load_course_metadata(course_dir: Path) -> dict[str, Any]:
    path = course_dir / COURSE_METADATA_FILE
    if not path.is_file():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def write_course_metadata(course_dir: Path, course: CourseRecord, payload: dict[str, Any]) -> None:
    metadata = {
        "course_id": course.course_id,
        "name": course.name,
        "group": course.group,
        **payload,
    }
    (course_dir / COURSE_METADATA_FILE).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_completed_course_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()

    completed: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("status") != "completed":
                continue
            course_id = str(payload.get("course_id", "")).strip()
            if course_id:
                completed.add(course_id)
    return completed


def course_complete(course_dir: Path, course_id: str, completed_course_ids: set[str] | None = None) -> bool:
    html_path = course_dir / f"{course_id}.html"
    if not nonempty_file(html_path):
        return False

    metadata = load_course_metadata(course_dir)
    if metadata.get("course_id") == course_id:
        return True

    return completed_course_ids is not None and course_id in completed_course_ids


def append_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def sleep_range(minimum: float, maximum: float, reason: str) -> float:
    seconds = minimum if maximum <= minimum else random.uniform(minimum, maximum)
    if seconds > 0:
        logging.info("Sleeping %.1fs (%s)", seconds, reason)
        time.sleep(seconds)
    return seconds


def backoff_seconds(attempt: int, base: float, maximum: float) -> float:
    return min(base * attempt, maximum)


def cookie_matches_domains(cookie: Any, domains: list[str]) -> bool:
    if not domains:
        return True
    domain = (cookie.domain or "").lstrip(".").lower()
    if not domain:
        return False
    return any(domain.endswith(value.lstrip(".").lower()) for value in domains)


def load_auth_cookies(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.browser_spec:
        cookies = load_browser_cookies(parse_browser_spec(args.browser_spec))
    else:
        cookies = load_cookies_txt(args.cookies)

    filtered = [cookie for cookie in cookies if cookie_matches_domains(cookie, args.cookie_domains)]
    if not filtered:
        raise SystemExit(
            "No cookies remained after domain filtering. "
            "Check --cookie-domain or the browser/profile you selected."
        )

    playwright_cookies: list[dict[str, Any]] = []
    for cookie in filtered:
        if not cookie.name or not cookie.domain:
            continue
        payload: dict[str, Any] = {
            "name": cookie.name,
            "value": cookie.value or "",
            "domain": cookie.domain,
            "path": cookie.path or "/",
            "secure": bool(cookie.secure),
            "httpOnly": bool(cookie._rest.get("HttpOnly")) if hasattr(cookie, "_rest") else False,
        }
        if cookie.expires is not None:
            payload["expires"] = float(cookie.expires)
        playwright_cookies.append(payload)

    if not playwright_cookies:
        raise SystemExit("No valid cookies were available to import into Playwright")

    return playwright_cookies


def is_login_page(page: Page) -> bool:
    url = page.url.lower()
    if "login" in url or "signin" in url:
        return True

    try:
        if page.locator("input[type='password']").count():
            return True
    except Exception:
        return False

    return False


def _check_navigation_response(response: Any, url: str) -> None:
    if response is None:
        return

    status = response.status
    if status == 429:
        raise RetryableCaptureError(f"429 Too Many Requests for {url}")
    if status >= 500:
        raise RetryableCaptureError(f"HTTP {status} for {url}")
    if status in (401, 403):
        raise AuthenticationRequiredError(f"HTTP {status} for {url}")


def _settle_page(page: Page, settle_wait_ms: int) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeoutError:
        pass
    if settle_wait_ms > 0:
        page.wait_for_timeout(settle_wait_ms)


def ensure_settings_ready(page: Page, timeout_ms: int) -> None:
    try:
        page.locator(CONFIGURE_BUTTON_SELECTOR).wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        if is_login_page(page):
            raise AuthenticationRequiredError(
                f"Page {page.url} appears to be unauthenticated; login form detected"
            ) from exc
        raise RetryableCaptureError(
            f"Timed out waiting for {CONFIGURE_BUTTON_SELECTOR} on {page.url}"
        ) from exc


def ensure_progress_ready(page: Page, timeout_ms: int) -> None:
    try:
        page.locator("body").wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        if is_login_page(page):
            raise AuthenticationRequiredError(
                f"Page {page.url} appears to be unauthenticated; login form detected"
            ) from exc
        raise RetryableCaptureError(
            f"Timed out waiting for progress content on {page.url}"
        ) from exc


def open_course_dialog(page: Page, timeout_ms: int) -> None:
    page.locator(CONFIGURE_BUTTON_SELECTOR).click(timeout=timeout_ms)
    page.locator(COURSE_DIALOG_SELECTOR).wait_for(state="visible", timeout=timeout_ms)
    page.locator(COURSE_SELECT_SELECTOR).wait_for(state="visible", timeout=timeout_ms)
    page.locator(BUTTON_BAR_SELECTOR).wait_for(state="visible", timeout=timeout_ms)


def course_records_from_dialog_state(payload: dict[str, Any]) -> tuple[str | None, list[CourseRecord]]:
    selected_raw = str(payload.get("selected", "") or "").strip()
    selected = selected_raw or None
    options_payload = payload.get("options")
    if not isinstance(options_payload, list):
        raise RetryableCaptureError("Course dialog did not expose a readable options list")

    courses: list[CourseRecord] = []
    seen_ids: set[str] = set()
    for item in options_payload:
        if not isinstance(item, dict):
            continue
        course_id = str(item.get("value", "") or "").strip()
        name = str(item.get("label", "") or "").strip()
        if not course_id or not name or bool(item.get("disabled")):
            continue
        if course_id in seen_ids:
            continue
        group_raw = item.get("group")
        group = str(group_raw).strip() if group_raw is not None and str(group_raw).strip() else None
        courses.append(CourseRecord(course_id=course_id, name=name, group=group))
        seen_ids.add(course_id)

    if not courses:
        raise RetryableCaptureError("No selectable courses were found in the configure-course dialog")

    return selected, courses


def load_available_courses(page: Page, args: argparse.Namespace) -> tuple[str | None, list[CourseRecord]]:
    response = page.goto(args.settings_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    _check_navigation_response(response, args.settings_url)
    _settle_page(page, args.settle_wait_ms)
    ensure_settings_ready(page, args.timeout_ms)
    open_course_dialog(page, args.timeout_ms)

    payload = page.locator(COURSE_SELECT_SELECTOR).evaluate(
        """select => ({
            selected: select.value || "",
            options: Array.from(select.options).map(option => ({
                value: option.value || "",
                label: (option.textContent || "").trim(),
                disabled: !!option.disabled,
                group: option.parentElement && option.parentElement.tagName === "OPTGROUP"
                    ? option.parentElement.label || ""
                    : "",
            })),
        })"""
    )
    if not isinstance(payload, dict):
        raise RetryableCaptureError("Course dialog returned an unreadable payload")
    return course_records_from_dialog_state(payload)


def switch_course(page: Page, course: CourseRecord, args: argparse.Namespace) -> None:
    response = page.goto(args.settings_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    _check_navigation_response(response, args.settings_url)
    _settle_page(page, args.settle_wait_ms)
    ensure_settings_ready(page, args.timeout_ms)
    open_course_dialog(page, args.timeout_ms)

    select = page.locator(COURSE_SELECT_SELECTOR)
    current_course_id = select.input_value(timeout=args.timeout_ms).strip()
    if current_course_id == course.course_id:
        page.locator(CANCEL_BUTTON_SELECTOR).click(timeout=args.timeout_ms)
        page.locator(COURSE_DIALOG_SELECTOR).wait_for(state="hidden", timeout=args.timeout_ms)
        return

    selected = select.select_option(value=course.course_id, timeout=args.timeout_ms)
    if course.course_id not in selected:
        raise RetryableCaptureError(f"Failed to select course {course.course_id} in the configure-course dialog")

    if args.settle_wait_ms > 0:
        page.wait_for_timeout(args.settle_wait_ms)

    page.locator(SAVE_BUTTON_SELECTOR).click(timeout=args.timeout_ms)
    page.locator(COURSE_DIALOG_SELECTOR).wait_for(state="hidden", timeout=args.timeout_ms)
    try:
        page.wait_for_function(
            """({selector, courseName}) => {
                const element = document.querySelector(selector);
                return !!element && (element.textContent || "").includes(courseName);
            }""",
            {"selector": CURRENT_COURSE_SELECTOR, "courseName": course.name},
            timeout=args.timeout_ms,
        )
    except PlaywrightTimeoutError as exc:
        raise RetryableCaptureError(
            f"Course selection did not appear to persist for {course.course_id} {course.name}"
        ) from exc

    if args.settle_wait_ms > 0:
        page.wait_for_timeout(args.settle_wait_ms)


def capture_course_once(
    page: Page,
    course: CourseRecord,
    course_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    switch_course(page, course, args)

    url = progress_url(course.course_id, args)
    response = page.goto(url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    _check_navigation_response(response, url)
    _settle_page(page, args.settle_wait_ms)
    ensure_progress_ready(page, args.timeout_ms)
    if is_login_page(page):
        raise AuthenticationRequiredError(f"Math Academy redirected to a login page for {url}")

    course_dir.mkdir(parents=True, exist_ok=True)
    html_path = course_dir / f"{course.course_id}.html"
    html_path.write_text(page.content(), encoding="utf-8")

    metadata = {
        "html_path": str(html_path),
        "progress_url": url,
        "final_url": page.url,
    }
    write_course_metadata(course_dir, course, metadata)
    return metadata


def capture_course_with_retries(
    page: Page,
    course: CourseRecord,
    course_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    attempts = args.retries + 1
    for attempt in range(1, attempts + 1):
        try:
            return capture_course_once(page, course, course_dir, args)
        except AuthenticationRequiredError:
            raise
        except RetryableCaptureError:
            if attempt >= attempts:
                raise
            delay = backoff_seconds(attempt, args.retry_base_seconds, args.retry_max_seconds)
            logging.warning(
                "Retryable failure on course %s (%s/%s). Backing off for %.1fs",
                course.course_id,
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)
            page.goto("about:blank", wait_until="load", timeout=args.timeout_ms)


def build_context(
    playwright: Any,
    cookies: list[dict[str, Any]],
    args: argparse.Namespace,
) -> tuple[Any, BrowserContext]:
    browser_type = getattr(playwright, args.engine)
    browser = browser_type.launch(headless=not args.headed)
    context = browser.new_context(
        viewport={
            "width": args.viewport_width,
            "height": args.viewport_height,
        },
        device_scale_factor=args.device_scale_factor,
        locale="en-US",
    )
    context.add_cookies(cookies)
    return browser, context


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    if args.dry_run:
        logging.info("Dry run only")
        logging.info("Settings URL: %s", args.settings_url)
        logging.info("Progress URL template: %s", args.progress_url_template)
        logging.info("Output root: %s", args.output_root)
        if args.course_ids:
            logging.info("Filtered course IDs: %s", ", ".join(args.course_ids))
        if args.start_at:
            logging.info("Start at course: %s", args.start_at)
        if args.limit is not None:
            logging.info("Limit: %d", args.limit)
        if args.restore_original_course:
            logging.info("Restore course: %s", args.restore_course_id)
        return 0

    args.output_root.mkdir(parents=True, exist_ok=True)
    state_file = args.state_file or (args.output_root / DEFAULT_STATE_FILE)
    completed_course_ids = load_completed_course_ids(state_file)

    cookies = load_auth_cookies(args)
    logging.info("Loaded %d auth cookies into Playwright", len(cookies))

    successes = 0
    failures = 0
    skipped = 0
    available_courses: list[CourseRecord] = []

    with sync_playwright() as playwright:
        browser, context = build_context(playwright, cookies, args)
        page = context.new_page()
        page.set_default_timeout(args.timeout_ms)

        try:
            _, available_courses = load_available_courses(page, args)
            selected = select_courses(available_courses, args)
            if not selected:
                logging.warning("No courses matched the requested filters")
                return 0

            logging.info("Discovered %d courses in the configure-course dialog", len(available_courses))
            progress = tqdm(
                total=len(selected),
                desc="courses",
                unit="course",
                dynamic_ncols=True,
                disable=args.no_progress or not sys.stderr.isatty(),
            )

            try:
                for index, course in enumerate(selected, start=1):
                    progress.set_description(f"course {course.course_id}")
                    course_dir = args.output_root / course.course_id

                    if not args.force and course_complete(course_dir, course.course_id, completed_course_ids):
                        logging.info(
                            "Skipping %s (%s): output already looks complete",
                            course.course_id,
                            course.name,
                        )
                        skipped += 1
                        append_state(
                            state_file,
                            {
                                "course_id": course.course_id,
                                "name": course.name,
                                "group": course.group,
                                "status": "skipped",
                                "ts": int(time.time()),
                            },
                        )
                        progress.update(1)
                        progress.set_postfix(success=successes, failed=failures, skipped=skipped)
                        continue

                    logging.info("[%d/%d] Capturing %s %s", index, len(selected), course.course_id, course.name)
                    append_state(
                        state_file,
                        {
                            "course_id": course.course_id,
                            "name": course.name,
                            "group": course.group,
                            "status": "started",
                            "ts": int(time.time()),
                            "progress_url": progress_url(course.course_id, args),
                        },
                    )

                    try:
                        result = capture_course_with_retries(page, course, course_dir, args)
                    except AuthenticationRequiredError as exc:
                        failures += 1
                        logging.error("Stopping batch: %s", exc)
                        append_state(
                            state_file,
                            {
                                "course_id": course.course_id,
                                "name": course.name,
                                "group": course.group,
                                "status": "auth_failed",
                                "error": str(exc),
                                "ts": int(time.time()),
                            },
                        )
                        progress.update(1)
                        progress.set_postfix(success=successes, failed=failures, skipped=skipped)
                        return 2
                    except Exception as exc:
                        failures += 1
                        logging.exception("Capture failed for %s", course.course_id)
                        append_state(
                            state_file,
                            {
                                "course_id": course.course_id,
                                "name": course.name,
                                "group": course.group,
                                "status": "failed",
                                "error": str(exc),
                                "ts": int(time.time()),
                            },
                        )
                        progress.update(1)
                        progress.set_postfix(success=successes, failed=failures, skipped=skipped)
                        if args.stop_on_error:
                            return 1
                        sleep_range(args.rest_min, args.rest_max, f"{course.course_id} failure cooldown")
                        continue

                    successes += 1
                    completed_course_ids.add(course.course_id)
                    append_state(
                        state_file,
                        {
                            "course_id": course.course_id,
                            "name": course.name,
                            "group": course.group,
                            "status": "completed",
                            "ts": int(time.time()),
                            **result,
                        },
                    )
                    progress.update(1)
                    progress.set_postfix(success=successes, failed=failures, skipped=skipped)

                    is_last_course = index == len(selected)
                    if not is_last_course:
                        sleep_range(args.sleep_course_min, args.sleep_course_max, f"{course.course_id} course pacing")
                        if args.rest_every and successes % args.rest_every == 0:
                            sleep_range(args.rest_min, args.rest_max, "periodic cooldown")
            finally:
                progress.close()

            if args.restore_original_course:
                restore_course = next(
                    (course for course in available_courses if course.course_id == args.restore_course_id),
                    None,
                )
                if restore_course is None:
                    logging.warning(
                        "Restore course %s was not found in the configure-course dialog",
                        args.restore_course_id,
                    )
                else:
                    try:
                        logging.info("Restoring course %s %s", restore_course.course_id, restore_course.name)
                        switch_course(page, restore_course, args)
                    except Exception:
                        logging.exception("Failed to restore course %s", restore_course.course_id)
        finally:
            context.close()
            browser.close()

    logging.info("Finished. successes=%d failures=%d skipped=%d", successes, failures, skipped)
    return 0 if failures == 0 else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
