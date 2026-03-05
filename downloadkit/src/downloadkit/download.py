"""Download orchestration helpers for downloadkit."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import requests
from requestkit import RequestClient, ResponseValidationError, SessionConfig

from .paths import ensure_parent, remove_if_exists
from .resume import build_resume_state
from .validate import DownloadValidationError, validate_file_signature, validate_response_metadata


@dataclass(slots=True)
class DownloadConfig:
    output: str | Path
    overwrite: bool = False
    resume: bool = True
    atomic: bool = True
    chunk_size: int = 32_768
    rate_limit: int | None = None
    expected_content_type: str | tuple[str, ...] | None = None
    validate_signature: bool = True
    html_is_error: bool = True
    headers: dict[str, str] = field(default_factory=dict)
    fallback_urls: tuple[str, ...] = field(default_factory=tuple)
    request: SessionConfig = field(default_factory=SessionConfig)

    def __post_init__(self) -> None:
        self.output = Path(self.output)
        self.fallback_urls = tuple(self.fallback_urls)


@dataclass(slots=True, frozen=True)
class DownloadResult:
    status: str
    source_url: str
    used_url: str
    final_url: str
    output: Path
    bytes_written: int
    attempts: int
    resumed: bool
    used_fallback: bool
    content_type: str | None


class DownloadError(RuntimeError):
    """Raised when all candidate URLs fail."""


def _parse_rate(rate: int | None) -> int | None:
    return None if rate is None or rate <= 0 else int(rate)


def _throttle(
    *,
    rate_limit: int | None,
    bytes_written: int,
    started_at: float,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> None:
    if not rate_limit:
        return

    elapsed = clock() - started_at
    target = bytes_written / rate_limit
    delay = target - elapsed
    if delay > 0:
        sleeper(delay)


def _write_response_to_file(
    response: requests.Response,
    output: Path,
    config: DownloadConfig,
    *,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> tuple[int, bool]:
    resume_state = build_resume_state(output, resume=config.resume)
    part_path = resume_state.part_path

    ensure_parent(output)

    requested_range = response.request.headers.get("Range")
    resumed = resume_state.resumed and requested_range is not None and response.status_code == 206

    if requested_range and response.status_code != 206:
        resume_state = build_resume_state(output, resume=False)
        resumed = False

    target_path = part_path if (config.atomic or config.resume) else output
    mode = resume_state.mode if resumed else "wb"
    bytes_written = resume_state.offset if resumed else 0
    rate_limit = _parse_rate(config.rate_limit)
    chunks = response.iter_content(chunk_size=config.chunk_size)
    started_at = clock()

    with open(target_path, mode) as handle:
        first_chunk = b""
        try:
            first_chunk = next(chunks)
        except StopIteration:
            first_chunk = b""

        if first_chunk:
            if not resumed:
                validate_file_signature(
                    output,
                    first_chunk,
                    validate_signature=config.validate_signature,
                )
            handle.write(first_chunk)
            bytes_written += len(first_chunk)
            _throttle(
                rate_limit=rate_limit,
                bytes_written=bytes_written,
                started_at=started_at,
                clock=clock,
                sleeper=sleeper,
            )

        for chunk in chunks:
            if not chunk:
                continue
            handle.write(chunk)
            bytes_written += len(chunk)
            _throttle(
                rate_limit=rate_limit,
                bytes_written=bytes_written,
                started_at=started_at,
                clock=clock,
                sleeper=sleeper,
            )

        handle.flush()
        os.fsync(handle.fileno())

    if target_path != output:
        os.replace(target_path, output)
    return bytes_written, resumed


def _fetch_one(
    url: str,
    config: DownloadConfig,
    *,
    client: RequestClient,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> DownloadResult:
    output = Path(config.output)
    part_path = build_resume_state(output, resume=False).part_path

    if output.exists() and not config.overwrite:
        return DownloadResult(
            status="skipped",
            source_url=url,
            used_url=url,
            final_url=str(output),
            output=output,
            bytes_written=output.stat().st_size,
            attempts=0,
            resumed=False,
            used_fallback=False,
            content_type=None,
        )

    if config.overwrite:
        remove_if_exists(output)
        if not config.resume:
            remove_if_exists(part_path)

    attempts = 0
    while True:
        attempts += 1
        resume_state = build_resume_state(output, resume=config.resume)
        headers = dict(config.headers)
        if resume_state.use_range:
            headers["Range"] = f"bytes={resume_state.offset}-"

        response = client.request(
            url,
            headers=headers,
            stream=True,
            expected_status=(200, 206),
        )

        try:
            validate_response_metadata(
                response,
                output,
                expected_content_type=config.expected_content_type,
                html_is_error=config.html_is_error,
            )
            bytes_written, resumed = _write_response_to_file(
                response,
                output,
                config,
                clock=clock,
                sleeper=sleeper,
            )
        except DownloadValidationError:
            response.close()
            raise
        except (requests.RequestException, OSError) as exc:
            response.close()
            if attempts > config.request.retries + 1:
                raise DownloadError(f"Failed to download {url}: {exc}") from exc
            sleeper(attempts)
            continue
        finally:
            response.close()

        status = "resumed" if resumed else "downloaded"
        return DownloadResult(
            status=status,
            source_url=url,
            used_url=url,
            final_url=response.url,
            output=output,
            bytes_written=bytes_written,
            attempts=attempts,
            resumed=resumed,
            used_fallback=False,
            content_type=response.headers.get("Content-Type"),
        )


def fetch(
    url: str,
    config: DownloadConfig,
    *,
    client: RequestClient | None = None,
    session: requests.Session | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> DownloadResult:
    """Download a URL to disk, optionally trying fallback URLs."""

    if client is None:
        client = RequestClient(config.request, session=session, clock=clock, sleeper=sleeper)

    candidates = (url, *config.fallback_urls)
    errors: list[str] = []

    for index, candidate in enumerate(candidates):
        try:
            result = _fetch_one(candidate, config, client=client, clock=clock, sleeper=sleeper)
        except (DownloadError, DownloadValidationError, ResponseValidationError) as exc:
            errors.append(f"{candidate}: {exc}")
            continue

        if index:
            return DownloadResult(
                status=result.status,
                source_url=url,
                used_url=candidate,
                final_url=result.final_url,
                output=result.output,
                bytes_written=result.bytes_written,
                attempts=result.attempts,
                resumed=result.resumed,
                used_fallback=True,
                content_type=result.content_type,
            )
        return result

    joined = "; ".join(errors) if errors else f"No candidate URL succeeded for {url}"
    raise DownloadError(joined)
