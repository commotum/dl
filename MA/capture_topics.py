#!/usr/bin/env python3
"""Capture hydrated Math Academy topic pages and screenshots."""

from __future__ import annotations

import argparse
import csv
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
DEFAULT_TOPICS_CSV = SCRIPT_DIR / "Topics.csv"
DEFAULT_TOPIC_JSON_DIR = SCRIPT_DIR / "Topic-JSON"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "captures"
DEFAULT_STATE_FILE = "_capture_state.jsonl"
CAPTURE_METADATA_FILE = "_capture_meta.json"


@dataclass(frozen=True)
class TopicRecord:
    topic_id: str
    name: str
    url: str


class CaptureError(RuntimeError):
    """Base class for capture failures."""


class RetryableCaptureError(CaptureError):
    """Temporary failure that can be retried after backing off."""


class AuthenticationRequiredError(CaptureError):
    """Raised when the page looks unauthenticated or blocked."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture hydrated Math Academy topic HTML and screenshots.",
    )
    parser.add_argument(
        "--topics-csv",
        type=Path,
        default=DEFAULT_TOPICS_CSV,
        help="Path to Topics.csv.",
    )
    parser.add_argument(
        "--topic-json-dir",
        type=Path,
        default=DEFAULT_TOPIC_JSON_DIR,
        help="Directory containing Topic-JSON manifests.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where topic capture folders will be created.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Optional JSONL state log path. Defaults to OUTPUT_ROOT/_capture_state.jsonl.",
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
        "--topic-id",
        dest="topic_ids",
        action="append",
        default=[],
        help="Specific topic ID to capture. Repeatable.",
    )
    selection.add_argument(
        "--start-at",
        help="Start processing at this topic ID within Topics.csv order.",
    )
    selection.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of topics to process after filtering.",
    )
    selection.add_argument(
        "--force",
        action="store_true",
        help="Recapture topics even if output files already look complete.",
    )
    selection.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print what would run without opening the browser.",
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
        help="Playwright device scale factor for higher-density screenshots.",
    )
    browser.add_argument(
        "--timeout-ms",
        type=int,
        default=45_000,
        help="Per-operation timeout in milliseconds.",
    )
    browser.add_argument(
        "--render-wait-ms",
        type=int,
        default=500,
        help="Small wait after scrolling an element into view before screenshotting it.",
    )

    pacing = parser.add_argument_group("pacing")
    pacing.add_argument(
        "--sleep-topic-min",
        type=float,
        default=10.0,
        help="Minimum seconds to sleep between topics.",
    )
    pacing.add_argument(
        "--sleep-topic-max",
        type=float,
        default=25.0,
        help="Maximum seconds to sleep between topics.",
    )
    pacing.add_argument(
        "--sleep-item-min",
        type=float,
        default=0.2,
        help="Minimum seconds to sleep between per-item captures.",
    )
    pacing.add_argument(
        "--sleep-item-max",
        type=float,
        default=0.8,
        help="Maximum seconds to sleep between per-item captures.",
    )
    pacing.add_argument(
        "--rest-every",
        type=int,
        default=20,
        help="Take a longer rest after every N successfully captured topics. Set 0 to disable.",
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
        help="Number of retries for transient topic-level failures.",
    )
    pacing.add_argument(
        "--retry-base-seconds",
        type=float,
        default=30.0,
        help="Base backoff seconds for transient topic-level failures.",
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
        ("sleep_topic_min", "sleep_topic_max"),
        ("sleep_item_min", "sleep_item_max"),
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


def load_topics(path: Path) -> list[TopicRecord]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            TopicRecord(
                topic_id=row["topic-id"].strip(),
                name=row["name"].strip(),
                url=row["url"].strip(),
            )
            for row in reader
        ]


def select_topics(topics: list[TopicRecord], args: argparse.Namespace) -> list[TopicRecord]:
    selected = topics

    if args.topic_ids:
        wanted = {value.strip() for value in args.topic_ids}
        selected = [topic for topic in selected if topic.topic_id in wanted]

    if args.start_at:
        start_index = next(
            (index for index, topic in enumerate(selected) if topic.topic_id == args.start_at),
            None,
        )
        if start_index is None:
            raise SystemExit(f"--start-at topic {args.start_at!r} was not found after filtering")
        selected = selected[start_index:]

    if args.limit is not None:
        selected = selected[: args.limit]

    return selected


def load_manifest(topic_json_dir: Path, topic_id: str) -> dict[str, Any]:
    path = topic_json_dir / f"{topic_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def lesson_screenshot_paths(topic_dir: Path) -> list[Path]:
    return sorted(path for path in topic_dir.glob("*.png") if path.name != "00-TOC.png")


def load_capture_metadata(topic_dir: Path) -> dict[str, Any]:
    path = topic_dir / CAPTURE_METADATA_FILE
    if not path.is_file():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def write_capture_metadata(topic_dir: Path, topic_id: str, filenames: list[str]) -> None:
    payload = {
        "topic_id": topic_id,
        "lesson_count": len(filenames),
        "filenames": filenames,
    }
    (topic_dir / CAPTURE_METADATA_FILE).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_completed_lesson_counts(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}

    counts: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if payload.get("status") != "completed":
                continue

            topic_id = str(payload.get("topic_id", "")).strip()
            lesson_count = payload.get("lesson_count")
            if topic_id and isinstance(lesson_count, int):
                counts[topic_id] = lesson_count

    return counts


def topic_complete(
    topic_dir: Path,
    manifest: dict[str, Any],
    completed_lesson_count: int | None = None,
) -> bool:
    html_path = topic_dir / f"{manifest['topic_id']}.html"
    toc_path = topic_dir / "00-TOC.png"
    lesson_targets = manifest.get("capture_targets", {}).get("lesson_items", [])

    if not nonempty_file(html_path):
        return False
    if not nonempty_file(toc_path):
        return False

    for item in lesson_targets:
        filename = item.get("filename")
        if not filename:
            return False
        path = topic_dir / filename
        if not nonempty_file(path):
            break
    else:
        return True

    metadata = load_capture_metadata(topic_dir)
    metadata_filenames = metadata.get("filenames")
    if isinstance(metadata_filenames, list) and metadata_filenames:
        if all(isinstance(filename, str) and nonempty_file(topic_dir / filename) for filename in metadata_filenames):
            lesson_count = metadata.get("lesson_count")
            return not isinstance(lesson_count, int) or lesson_count == len(metadata_filenames)

    if completed_lesson_count is None:
        return False

    lesson_paths = lesson_screenshot_paths(topic_dir)
    if len(lesson_paths) != completed_lesson_count:
        return False
    if not all(nonempty_file(path) for path in lesson_paths):
        return False

    return True


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


def ensure_topic_ready(page: Page, timeout_ms: int) -> None:
    try:
        page.locator("#lessonContent").wait_for(state="visible", timeout=timeout_ms)
        page.locator("#sidebar").wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        if is_login_page(page):
            raise AuthenticationRequiredError(
                f"Page {page.url} appears to be unauthenticated; login form detected"
            ) from exc
        raise RetryableCaptureError(
            f"Timed out waiting for #lessonContent/#sidebar on {page.url}"
        ) from exc


def visible_structural_items(page: Page) -> list[Locator]:
    container = page.locator("#lessonContent")
    items = container.locator(":scope > *")
    visible: list[Locator] = []
    count = items.count()
    for index in range(count):
        locator = items.nth(index)
        try:
            box = locator.bounding_box()
        except Exception:
            continue
        if box and box["width"] > 0 and box["height"] > 0:
            visible.append(locator)
    return visible


def resolved_item_targets(page: Page, manifest: dict[str, Any]) -> list[tuple[str, Locator]]:
    lesson_targets = manifest.get("capture_targets", {}).get("lesson_items", [])
    structural = visible_structural_items(page)
    topic_id = manifest.get("topic_id", "unknown")

    if not structural:
        raise RetryableCaptureError(f"No visible lesson items found for topic {topic_id}")

    def structural_targets() -> list[tuple[str, Locator]]:
        return [
            (f"{index + 1:02d}-structural-{index + 1}.png", locator)
            for index, locator in enumerate(structural)
        ]

    if lesson_targets:
        if len(structural) != len(lesson_targets):
            logging.warning(
                "Topic %s manifest expects %d lesson items but live DOM has %d; "
                "falling back to structural targeting",
                topic_id,
                len(lesson_targets),
                len(structural),
            )
            return structural_targets()

        resolved: list[tuple[str, Locator]] = []
        for index, item in enumerate(lesson_targets):
            filename = item.get("filename") or f"{index + 1:02d}-item-{index + 1}.png"
            selector = item.get("selector")
            if not selector:
                logging.warning(
                    "Topic %s manifest item %d is missing a selector; falling back to structural targeting",
                    topic_id,
                    index + 1,
                )
                return structural_targets()

            candidate = page.locator(selector).first
            try:
                if not candidate.count():
                    logging.warning(
                        "Topic %s manifest selector %r failed for item %d; "
                        "falling back to structural targeting",
                        topic_id,
                        selector,
                        index + 1,
                    )
                    return structural_targets()
            except Exception:
                logging.warning(
                    "Topic %s manifest selector %r errored for item %d; "
                    "falling back to structural targeting",
                    topic_id,
                    selector,
                    index + 1,
                )
                return structural_targets()

            resolved.append((filename, candidate))
        return resolved

    return structural_targets()


def screenshot_locator(locator: Locator, path: Path, render_wait_ms: int, timeout_ms: int) -> None:
    locator.scroll_into_view_if_needed(timeout=timeout_ms)
    locator.page.wait_for_timeout(render_wait_ms)
    box = locator.bounding_box()
    if not box or box["width"] <= 0 or box["height"] <= 0:
        raise RetryableCaptureError(f"Target {path.name} is not visible or has zero size")
    locator.screenshot(
        path=str(path),
        timeout=timeout_ms,
        animations="disabled",
        scale="device",
    )


def capture_topic_once(
    page: Page,
    topic: TopicRecord,
    manifest: dict[str, Any],
    topic_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    response = page.goto(topic.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    if response is not None:
        status = response.status
        if status == 429:
            raise RetryableCaptureError(f"429 Too Many Requests for {topic.url}")
        if status >= 500:
            raise RetryableCaptureError(f"HTTP {status} for {topic.url}")
        if status in (401, 403):
            raise AuthenticationRequiredError(f"HTTP {status} for {topic.url}")

    try:
        page.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeoutError:
        pass

    ensure_topic_ready(page, args.timeout_ms)
    if is_login_page(page):
        raise AuthenticationRequiredError(f"Math Academy redirected to a login page for {topic.url}")

    topic_dir.mkdir(parents=True, exist_ok=True)
    html_path = topic_dir / f"{topic.topic_id}.html"
    html_path.write_text(page.content(), encoding="utf-8")

    toc_path = topic_dir / "00-TOC.png"
    screenshot_locator(page.locator("#sidebar"), toc_path, args.render_wait_ms, args.timeout_ms)
    sleep_range(args.sleep_item_min, args.sleep_item_max, f"{topic.topic_id} toc")

    resolved_items = resolved_item_targets(page, manifest)
    for filename, locator in resolved_items:
        screenshot_locator(locator, topic_dir / filename, args.render_wait_ms, args.timeout_ms)
        sleep_range(args.sleep_item_min, args.sleep_item_max, f"{topic.topic_id} lesson item")

    write_capture_metadata(topic_dir, topic.topic_id, [filename for filename, _ in resolved_items])

    return {
        "html_path": str(html_path),
        "toc_path": str(toc_path),
        "lesson_count": len(resolved_items),
        "final_url": page.url,
    }


def capture_topic_with_retries(
    page: Page,
    topic: TopicRecord,
    manifest: dict[str, Any],
    topic_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    attempts = args.retries + 1
    for attempt in range(1, attempts + 1):
        try:
            return capture_topic_once(page, topic, manifest, topic_dir, args)
        except AuthenticationRequiredError:
            raise
        except RetryableCaptureError:
            if attempt >= attempts:
                raise
            delay = backoff_seconds(attempt, args.retry_base_seconds, args.retry_max_seconds)
            logging.warning(
                "Retryable failure on topic %s (%s/%s). Backing off for %.1fs",
                topic.topic_id,
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

    topics = load_topics(args.topics_csv)
    selected = select_topics(topics, args)
    if not selected:
        logging.warning("No topics matched the requested filters")
        return 0

    args.output_root.mkdir(parents=True, exist_ok=True)
    state_file = args.state_file or (args.output_root / DEFAULT_STATE_FILE)
    completed_lesson_counts = load_completed_lesson_counts(state_file)

    if args.dry_run:
        logging.info("Dry run only")
        logging.info("Topics CSV: %s", args.topics_csv)
        logging.info("Topic JSON dir: %s", args.topic_json_dir)
        logging.info("Output root: %s", args.output_root)
        logging.info("Selected topics: %d", len(selected))
        for topic in selected[:10]:
            logging.info("Would capture %s %s", topic.topic_id, topic.name)
        if len(selected) > 10:
            logging.info("... and %d more", len(selected) - 10)
        return 0

    cookies = load_auth_cookies(args)
    logging.info("Loaded %d auth cookies into Playwright", len(cookies))

    successes = 0
    failures = 0
    skipped = 0

    with sync_playwright() as playwright:
        browser, context = build_context(playwright, cookies, args)
        page = context.new_page()
        page.set_default_timeout(args.timeout_ms)
        progress = tqdm(
            total=len(selected),
            desc="topics",
            unit="topic",
            dynamic_ncols=True,
            disable=args.no_progress or not sys.stderr.isatty(),
        )

        try:
            for index, topic in enumerate(selected, start=1):
                progress.set_description(f"topic {topic.topic_id}")
                manifest = load_manifest(args.topic_json_dir, topic.topic_id)
                topic_dir = args.output_root / topic.topic_id

                if not args.force and topic_complete(
                    topic_dir,
                    manifest,
                    completed_lesson_counts.get(topic.topic_id),
                ):
                    logging.info("Skipping %s (%s): output already looks complete", topic.topic_id, topic.name)
                    skipped += 1
                    append_state(
                        state_file,
                        {
                            "topic_id": topic.topic_id,
                            "name": topic.name,
                            "status": "skipped",
                            "ts": int(time.time()),
                        },
                    )
                    progress.update(1)
                    progress.set_postfix(success=successes, failed=failures, skipped=skipped)
                    continue

                logging.info("[%d/%d] Capturing %s %s", index, len(selected), topic.topic_id, topic.name)
                append_state(
                    state_file,
                    {
                        "topic_id": topic.topic_id,
                        "name": topic.name,
                        "status": "started",
                        "ts": int(time.time()),
                        "url": topic.url,
                    },
                )

                try:
                    result = capture_topic_with_retries(page, topic, manifest, topic_dir, args)
                except AuthenticationRequiredError as exc:
                    failures += 1
                    logging.error("Stopping batch: %s", exc)
                    append_state(
                        state_file,
                        {
                            "topic_id": topic.topic_id,
                            "name": topic.name,
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
                    logging.exception("Capture failed for %s", topic.topic_id)
                    append_state(
                        state_file,
                        {
                            "topic_id": topic.topic_id,
                            "name": topic.name,
                            "status": "failed",
                            "error": str(exc),
                            "ts": int(time.time()),
                        },
                    )
                    progress.update(1)
                    progress.set_postfix(success=successes, failed=failures, skipped=skipped)
                    if args.stop_on_error:
                        return 1
                    sleep_range(args.rest_min, args.rest_max, f"{topic.topic_id} failure cooldown")
                    continue

                successes += 1
                completed_lesson_counts[topic.topic_id] = result["lesson_count"]
                append_state(
                    state_file,
                    {
                        "topic_id": topic.topic_id,
                        "name": topic.name,
                        "status": "completed",
                        "ts": int(time.time()),
                        **result,
                    },
                )
                progress.update(1)
                progress.set_postfix(success=successes, failed=failures, skipped=skipped)

                is_last_topic = index == len(selected)
                if not is_last_topic:
                    sleep_range(args.sleep_topic_min, args.sleep_topic_max, f"{topic.topic_id} topic pacing")
                    if args.rest_every and successes % args.rest_every == 0:
                        sleep_range(args.rest_min, args.rest_max, "periodic cooldown")
        finally:
            progress.close()
            context.close()
            browser.close()

    logging.info("Finished. successes=%d failures=%d skipped=%d", successes, failures, skipped)
    return 0 if failures == 0 else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
