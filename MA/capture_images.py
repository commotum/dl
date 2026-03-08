#!/usr/bin/env python3
"""Download Math Academy topic graphics directly from image src values."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from cookiekit import load_browser_cookies, load_cookies_txt, parse_browser_spec
from downloadkit.validate import detect_file_signature
from requestkit import RequestClient, SessionConfig, build_session, detect_challenge
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TOPICS_CSV = SCRIPT_DIR / "Topics.csv"
DEFAULT_IMAGES_CSV = SCRIPT_DIR / "Images.csv"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "graphics"
DEFAULT_STATE_FILE = "_image_state.jsonl"
IMAGE_METADATA_FILE = "_image_meta.json"
IMAGE_ACCEPT_HEADER = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
IMAGE_CONTENT_TYPE_EXTENSIONS = {
    "image/apng": "png",
    "image/avif": "avif",
    "image/bmp": "bmp",
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/svg+xml": "svg",
    "image/vnd.microsoft.icon": "ico",
    "image/webp": "webp",
    "image/x-icon": "ico",
}


@dataclass(frozen=True)
class TopicRecord:
    topic_id: str
    name: str
    url: str


@dataclass(frozen=True)
class ImageRecord:
    topic_id: str
    img_src: str


@dataclass(frozen=True)
class TopicImageJob:
    topic_id: str
    name: str
    url: str
    images: tuple[ImageRecord, ...]


class CaptureError(RuntimeError):
    """Base class for image-download failures."""


class RetryableCaptureError(CaptureError):
    """Temporary failure that can be retried after backing off."""


class AuthenticationRequiredError(CaptureError):
    """Raised when the response looks unauthenticated or blocked."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Math Academy topic graphics directly from image src values.",
    )
    parser.add_argument(
        "--topics-csv",
        type=Path,
        default=DEFAULT_TOPICS_CSV,
        help="Path to Topics.csv for topic names, referers, and ordering.",
    )
    parser.add_argument(
        "--images-csv",
        type=Path,
        default=DEFAULT_IMAGES_CSV,
        help="Path to Images.csv.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where topic image folders will be created.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Optional JSONL state log path. Defaults to OUTPUT_ROOT/_image_state.jsonl.",
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
        help="Specific topic ID to download. Repeatable.",
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
        help="Redownload topics even if image outputs already look complete.",
    )
    selection.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print what would run without making requests.",
    )

    request_group = parser.add_argument_group("request")
    request_group.add_argument(
        "--base-url",
        default="https://mathacademy.com",
        help="Base URL used to resolve relative image src values.",
    )
    request_group.add_argument(
        "--request-browser",
        choices=("chrome", "firefox"),
        default="chrome",
        help="Browser header preset for direct image requests.",
    )
    request_group.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds.",
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
        "--sleep-image-min",
        type=float,
        default=0.2,
        help="Minimum seconds to sleep between image downloads within a topic.",
    )
    pacing.add_argument(
        "--sleep-image-max",
        type=float,
        default=0.8,
        help="Maximum seconds to sleep between image downloads within a topic.",
    )
    pacing.add_argument(
        "--rest-every",
        type=int,
        default=20,
        help="Take a longer rest after every N successfully downloaded topics. Set 0 to disable.",
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
        help="Stop the batch on the first non-authentication download failure.",
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
        ("sleep_image_min", "sleep_image_max"),
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
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")

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


def load_images(path: Path) -> list[ImageRecord]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            ImageRecord(
                topic_id=row["topic-id"].strip(),
                img_src=row["img-src"].strip(),
            )
            for row in reader
        ]


def topic_sort_key(topic_id: str) -> tuple[int, int | str]:
    return (0, int(topic_id)) if topic_id.isdigit() else (1, topic_id)


def build_topic_jobs(
    topics: list[TopicRecord],
    images: list[ImageRecord],
    *,
    base_url: str,
) -> list[TopicImageJob]:
    grouped: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in images:
        grouped[record.topic_id].append(record)

    jobs: list[TopicImageJob] = []
    seen_topic_ids: set[str] = set()
    for topic in topics:
        topic_images = grouped.get(topic.topic_id)
        if not topic_images:
            continue
        jobs.append(
            TopicImageJob(
                topic_id=topic.topic_id,
                name=topic.name,
                url=topic.url,
                images=tuple(topic_images),
            )
        )
        seen_topic_ids.add(topic.topic_id)

    missing_topics = sorted(set(grouped) - seen_topic_ids, key=topic_sort_key)
    for topic_id in missing_topics:
        logging.warning(
            "Topic %s appears in Images.csv but not Topics.csv; using --base-url as the referer fallback",
            topic_id,
        )
        jobs.append(
            TopicImageJob(
                topic_id=topic_id,
                name="",
                url=base_url,
                images=tuple(grouped[topic_id]),
            )
        )

    return jobs


def select_jobs(jobs: list[TopicImageJob], args: argparse.Namespace) -> list[TopicImageJob]:
    selected = jobs

    if args.topic_ids:
        wanted = {value.strip() for value in args.topic_ids}
        selected = [job for job in selected if job.topic_id in wanted]

    if args.start_at:
        start_index = next(
            (index for index, job in enumerate(selected) if job.topic_id == args.start_at),
            None,
        )
        if start_index is None:
            raise SystemExit(f"--start-at topic {args.start_at!r} was not found after filtering")
        selected = selected[start_index:]

    if args.limit is not None:
        selected = selected[: args.limit]

    return selected


def image_stem(img_src: str) -> str:
    stem = Path(urlsplit(img_src).path).name.strip()
    if not stem:
        raise CaptureError(f"Could not derive a filename from img src {img_src!r}")
    return stem


def nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def image_file_candidates(topic_dir: Path, stem: str) -> list[Path]:
    candidates: list[Path] = []
    exact = topic_dir / stem
    if exact.is_file():
        candidates.append(exact)

    for path in sorted(topic_dir.glob(f"{stem}.*")):
        if not path.is_file():
            continue
        if path.name == IMAGE_METADATA_FILE:
            continue
        candidates.append(path)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path not in seen:
            deduped.append(path)
            seen.add(path)
    return deduped


def existing_image_path(topic_dir: Path, stem: str) -> Path | None:
    for path in image_file_candidates(topic_dir, stem):
        if nonempty_file(path):
            return path
    return None


def existing_topic_image_paths(topic_dir: Path) -> list[Path]:
    if not topic_dir.is_dir():
        return []

    return sorted(
        path
        for path in topic_dir.iterdir()
        if path.is_file() and path.name != IMAGE_METADATA_FILE and not path.name.startswith(".")
    )


def load_image_metadata(topic_dir: Path) -> dict[str, Any]:
    path = topic_dir / IMAGE_METADATA_FILE
    if not path.is_file():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def write_image_metadata(topic_dir: Path, topic_id: str, images: list[dict[str, Any]]) -> None:
    payload = {
        "topic_id": topic_id,
        "image_count": len(images),
        "images": images,
    }
    (topic_dir / IMAGE_METADATA_FILE).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_completed_image_counts(path: Path) -> dict[str, int]:
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
            image_count = payload.get("image_count")
            if topic_id and isinstance(image_count, int):
                counts[topic_id] = image_count

    return counts


def topic_complete(
    topic_dir: Path,
    images: tuple[ImageRecord, ...],
    completed_image_count: int | None = None,
) -> bool:
    if not topic_dir.is_dir():
        return False

    metadata = load_image_metadata(topic_dir)
    metadata_images = metadata.get("images")
    if isinstance(metadata_images, list) and metadata_images:
        filenames = [entry.get("filename") for entry in metadata_images if isinstance(entry, dict)]
        if len(filenames) == len(images) and all(
            isinstance(filename, str) and nonempty_file(topic_dir / filename)
            for filename in filenames
        ):
            image_count = metadata.get("image_count")
            return not isinstance(image_count, int) or image_count == len(filenames)

    stems = [image_stem(record.img_src) for record in images]
    if stems and all(existing_image_path(topic_dir, stem) for stem in stems):
        return True

    if completed_image_count is None:
        return False

    image_paths = existing_topic_image_paths(topic_dir)
    if len(image_paths) != completed_image_count:
        return False
    if not all(nonempty_file(path) for path in image_paths):
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


def load_auth_cookies(args: argparse.Namespace) -> list[Any]:
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
    return filtered


def build_client(cookies: list[Any], args: argparse.Namespace) -> RequestClient:
    config = SessionConfig(
        browser=args.request_browser,
        timeout=args.timeout_seconds,
        retries=0,
    )
    session = build_session(config)
    for cookie in cookies:
        session.cookies.set_cookie(cookie)
    return RequestClient(config, session=session)


def resolve_image_url(base_url: str, img_src: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", img_src)


def content_type_mime(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def looks_like_html(body: bytes) -> bool:
    snippet = body[:512].lstrip().lower()
    return snippet.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


def looks_like_svg(body: bytes) -> bool:
    snippet = body[:512].lstrip()
    lowered = snippet.lower()
    return lowered.startswith(b"<svg") or lowered.startswith(b"<?xml") and b"<svg" in lowered


def looks_like_login(response: requests.Response) -> bool:
    url = response.url.lower()
    if "login" in url or "signin" in url:
        return True

    body = (response.content or b"")[:8192].lower()
    return any(
        token in body
        for token in (
            b"type=\"password\"",
            b"type='password'",
            b"name=\"password\"",
            b"name='password'",
            b">log in<",
            b">login<",
            b">sign in<",
        )
    )


def infer_image_extension(content_type: str | None, body: bytes) -> str:
    signature = detect_file_signature(body)
    if signature in {"jpeg", "jpg"}:
        return "jpg"
    if signature is not None:
        return signature

    mime = content_type_mime(content_type)
    if mime in IMAGE_CONTENT_TYPE_EXTENSIONS:
        return IMAGE_CONTENT_TYPE_EXTENSIONS[mime]

    if looks_like_svg(body):
        return "svg"

    if mime.startswith("image/"):
        subtype = mime.split("/", 1)[1]
        if subtype.endswith("+xml"):
            subtype = subtype[: -len("+xml")]
        subtype = subtype.replace("jpeg", "jpg")
        if subtype:
            return subtype

    raise RetryableCaptureError("Response looked like an image but the file extension could not be inferred")


def response_looks_like_image(content_type: str | None, body: bytes) -> bool:
    if not body:
        return False
    if looks_like_html(body):
        return False
    if looks_like_svg(body):
        return True

    mime = content_type_mime(content_type)
    if mime.startswith("image/"):
        return True
    return detect_file_signature(body) is not None


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        tmp_path.write_bytes(data)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def fetch_image(
    client: RequestClient,
    record: ImageRecord,
    *,
    topic_url: str,
    topic_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    stem = image_stem(record.img_src)
    existing = existing_image_path(topic_dir, stem)
    if existing is not None and not args.force:
        return {
            "img_src": record.img_src,
            "filename": existing.name,
            "status": "existing",
            "bytes": existing.stat().st_size,
            "content_type": None,
            "final_url": None,
        }

    url = resolve_image_url(args.base_url, record.img_src)
    response: requests.Response | None = None
    try:
        response = client.request(
            url,
            headers={
                "Accept": IMAGE_ACCEPT_HEADER,
                "Referer": topic_url,
            },
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise RetryableCaptureError(f"Request failed for {url}: {exc}") from exc

    status = response.status_code
    if status == 429:
        raise RetryableCaptureError(f"429 Too Many Requests for {url}")
    if status >= 500:
        raise RetryableCaptureError(f"HTTP {status} for {url}")
    if status in (401, 403):
        raise AuthenticationRequiredError(f"HTTP {status} for {url}")
    if status != 200:
        raise CaptureError(f"Unexpected HTTP {status} for {url}")

    challenge = detect_challenge(response)
    if challenge:
        raise AuthenticationRequiredError(f"{challenge} at {response.url}")
    if looks_like_login(response):
        raise AuthenticationRequiredError(f"Image request for {url} appears to have been redirected to login")

    body = response.content or b""
    content_type = response.headers.get("Content-Type")
    if not response_looks_like_image(content_type, body):
        if content_type_mime(content_type) == "text/html":
            raise RetryableCaptureError(f"Received HTML instead of an image for {url}")
        raise CaptureError(f"Response for {url} did not look like an image")

    extension = infer_image_extension(content_type, body)
    output_path = topic_dir / f"{stem}.{extension}"
    atomic_write_bytes(output_path, body)

    return {
        "img_src": record.img_src,
        "filename": output_path.name,
        "status": "downloaded",
        "bytes": len(body),
        "content_type": content_type,
        "final_url": response.url,
    }


def download_topic_once(
    client: RequestClient,
    job: TopicImageJob,
    topic_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    topic_dir.mkdir(parents=True, exist_ok=True)

    image_entries: list[dict[str, Any]] = []
    bytes_written = 0
    downloaded_count = 0
    existing_count = 0

    for index, record in enumerate(job.images, start=1):
        entry = fetch_image(
            client,
            record,
            topic_url=job.url,
            topic_dir=topic_dir,
            args=args,
        )
        image_entries.append(entry)
        if entry["status"] == "downloaded":
            bytes_written += int(entry["bytes"])
            downloaded_count += 1
        else:
            existing_count += 1

        if index != len(job.images):
            sleep_range(args.sleep_image_min, args.sleep_image_max, f"{job.topic_id} image pacing")

    write_image_metadata(topic_dir, job.topic_id, image_entries)
    return {
        "image_count": len(image_entries),
        "downloaded_count": downloaded_count,
        "existing_count": existing_count,
        "bytes_written": bytes_written,
    }


def download_topic_with_retries(
    client: RequestClient,
    job: TopicImageJob,
    topic_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    attempts = args.retries + 1
    for attempt in range(1, attempts + 1):
        try:
            return download_topic_once(client, job, topic_dir, args)
        except AuthenticationRequiredError:
            raise
        except RetryableCaptureError:
            if attempt >= attempts:
                raise
            delay = backoff_seconds(attempt, args.retry_base_seconds, args.retry_max_seconds)
            logging.warning(
                "Retryable failure on topic %s (%s/%s). Backing off for %.1fs",
                job.topic_id,
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    topics = load_topics(args.topics_csv)
    images = load_images(args.images_csv)
    jobs = build_topic_jobs(topics, images, base_url=args.base_url)
    selected = select_jobs(jobs, args)
    if not selected:
        logging.warning("No topics matched the requested filters")
        return 0

    args.output_root.mkdir(parents=True, exist_ok=True)
    state_file = args.state_file or (args.output_root / DEFAULT_STATE_FILE)
    completed_image_counts = load_completed_image_counts(state_file)

    if args.dry_run:
        logging.info("Dry run only")
        logging.info("Topics CSV: %s", args.topics_csv)
        logging.info("Images CSV: %s", args.images_csv)
        logging.info("Output root: %s", args.output_root)
        logging.info("Selected topics: %d", len(selected))
        logging.info("Selected images: %d", sum(len(job.images) for job in selected))
        for job in selected[:10]:
            logging.info("Would download %s (%d images) %s", job.topic_id, len(job.images), job.name)
        if len(selected) > 10:
            logging.info("... and %d more", len(selected) - 10)
        return 0

    cookies = load_auth_cookies(args)
    client = build_client(cookies, args)
    logging.info("Loaded %d auth cookies into request session", len(cookies))

    successes = 0
    failures = 0
    skipped = 0
    progress = tqdm(
        total=len(selected),
        desc="topics",
        unit="topic",
        dynamic_ncols=True,
        disable=args.no_progress or not sys.stderr.isatty(),
    )

    try:
        for index, job in enumerate(selected, start=1):
            progress.set_description(f"topic {job.topic_id}")
            topic_dir = args.output_root / job.topic_id

            if not args.force and topic_complete(
                topic_dir,
                job.images,
                completed_image_counts.get(job.topic_id),
            ):
                logging.info(
                    "Skipping %s (%s): output already looks complete",
                    job.topic_id,
                    job.name,
                )
                skipped += 1
                append_state(
                    state_file,
                    {
                        "topic_id": job.topic_id,
                        "name": job.name,
                        "status": "skipped",
                        "ts": int(time.time()),
                    },
                )
                progress.update(1)
                progress.set_postfix(success=successes, failed=failures, skipped=skipped)
                continue

            logging.info("[%d/%d] Downloading %s %s", index, len(selected), job.topic_id, job.name)
            append_state(
                state_file,
                {
                    "topic_id": job.topic_id,
                    "name": job.name,
                    "status": "started",
                    "ts": int(time.time()),
                    "url": job.url,
                    "image_count": len(job.images),
                },
            )

            try:
                result = download_topic_with_retries(client, job, topic_dir, args)
            except AuthenticationRequiredError as exc:
                failures += 1
                logging.error("Stopping batch: %s", exc)
                append_state(
                    state_file,
                    {
                        "topic_id": job.topic_id,
                        "name": job.name,
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
                logging.exception("Download failed for %s", job.topic_id)
                append_state(
                    state_file,
                    {
                        "topic_id": job.topic_id,
                        "name": job.name,
                        "status": "failed",
                        "error": str(exc),
                        "ts": int(time.time()),
                    },
                )
                progress.update(1)
                progress.set_postfix(success=successes, failed=failures, skipped=skipped)
                if args.stop_on_error:
                    return 1
                sleep_range(args.rest_min, args.rest_max, f"{job.topic_id} failure cooldown")
                continue

            successes += 1
            completed_image_counts[job.topic_id] = int(result["image_count"])
            append_state(
                state_file,
                {
                    "topic_id": job.topic_id,
                    "name": job.name,
                    "status": "completed",
                    "ts": int(time.time()),
                    **result,
                },
            )
            progress.update(1)
            progress.set_postfix(success=successes, failed=failures, skipped=skipped)

            is_last_topic = index == len(selected)
            if not is_last_topic:
                sleep_range(args.sleep_topic_min, args.sleep_topic_max, f"{job.topic_id} topic pacing")
                if args.rest_every and successes % args.rest_every == 0:
                    sleep_range(args.rest_min, args.rest_max, "periodic cooldown")
    finally:
        progress.close()
        client.session.close()

    logging.info("Finished. successes=%d failures=%d skipped=%d", successes, failures, skipped)
    return 0 if failures == 0 else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
