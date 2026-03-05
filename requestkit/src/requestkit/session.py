"""Session-building helpers for requestkit."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import urllib3
from cookiekit import load_cookies_txt
from requests import Response
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    ContentDecodingError,
    Timeout,
)

from .challenge import detect_challenge
from .ratelimit import sleep as sleep_for
from .retry import RetryPolicy, retry_delay, should_retry_status

SUPPORTED_BROWSERS = {"chrome", "firefox"}


def _platform_tokens() -> tuple[str, str]:
    if os.name == "nt":
        return "Windows NT 10.0; Win64; x64", "Windows"
    if sys.platform == "darwin":
        return "Macintosh; Intel Mac OS X 15_0", "macOS"
    return "X11; Linux x86_64", "Linux"


try:
    _HAS_BROTLI = urllib3.response.brotli is not None
except AttributeError:
    _HAS_BROTLI = False

try:
    _HAS_ZSTD = urllib3.response.HAS_ZSTD
except AttributeError:
    _HAS_ZSTD = False


@dataclass(slots=True)
class SessionConfig:
    browser: str | None = None
    user_agent: str | None = None
    referer: str | None = None
    proxy: str | None = None
    timeout: float = 30.0
    retries: int = 4
    sleep_request: float = 0.0
    sleep_429: float = 60.0
    cookies: str | Path | None = None
    headers: dict[str, str] = field(default_factory=dict)
    verify: bool = True

    def __post_init__(self) -> None:
        if self.browser is not None:
            self.browser = self.browser.lower()
            if self.browser not in SUPPORTED_BROWSERS:
                supported = ", ".join(sorted(SUPPORTED_BROWSERS))
                raise ValueError(f"Unsupported browser preset '{self.browser}'. Expected one of: {supported}")


class ResponseValidationError(RuntimeError):
    """Raised when a response does not match expected status or content type."""


def _accept_encoding() -> str:
    values = ["gzip", "deflate"]
    if _HAS_BROTLI:
        values.append("br")
    if _HAS_ZSTD:
        values.append("zstd")
    return ", ".join(values)


def _browser_headers(browser: str | None) -> dict[str, str]:
    platform, platform_name = _platform_tokens()

    if browser == "chrome":
        return {
            "Connection": "keep-alive",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{platform_name}"',
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": (
                f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Dest": "empty",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": _accept_encoding(),
        }

    if browser == "firefox":
        return {
            "User-Agent": f"Mozilla/5.0 ({platform}; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": _accept_encoding(),
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers",
        }

    return {
        "User-Agent": f"Mozilla/5.0 ({platform}; rv:140.0) Gecko/20100101 Firefox/140.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": _accept_encoding(),
    }


def _load_cookies_into_session(session: requests.Session, path: str | Path) -> None:
    for cookie in load_cookies_txt(path):
        session.cookies.set_cookie(cookie)


def build_session(config: SessionConfig | None = None) -> requests.Session:
    config = config or SessionConfig()

    session = requests.Session()
    session.headers.clear()
    session.headers.update(_browser_headers(config.browser))
    if config.user_agent:
        session.headers["User-Agent"] = config.user_agent
    if config.referer:
        session.headers["Referer"] = config.referer
    if config.headers:
        session.headers.update(config.headers)

    if config.proxy:
        session.proxies.update({"http": config.proxy, "https": config.proxy})

    session.verify = config.verify

    if config.cookies:
        _load_cookies_into_session(session, config.cookies)

    return session


def _status_matches(status_code: int, expected_status: int | Collection[int] | None) -> bool:
    if expected_status is None:
        return True
    if isinstance(expected_status, int):
        return status_code == expected_status
    return status_code in expected_status


def _content_type_matches(content_type: str | None, expected_content_type: str | Collection[str] | None) -> bool:
    if expected_content_type is None:
        return True
    if not content_type:
        return False

    lowered = content_type.lower()
    if isinstance(expected_content_type, str):
        return expected_content_type.lower() in lowered
    return any(part.lower() in lowered for part in expected_content_type)


class RequestClient:
    """Thin stateful wrapper around ``requests.Session``."""

    def __init__(
        self,
        config: SessionConfig | None = None,
        *,
        session: requests.Session | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or SessionConfig()
        self.session = session or build_session(self.config)
        self._clock = clock
        self._sleep = sleeper
        self._last_request_at: float | None = None
        self._retry_policy = RetryPolicy(retries=self.config.retries)

    def _pace(self) -> None:
        if self.config.sleep_request <= 0 or self._last_request_at is None:
            return

        elapsed = self._clock() - self._last_request_at
        remaining = self.config.sleep_request - elapsed
        if remaining > 0:
            sleep_for(remaining, "request", sleeper=self._sleep)

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        data: Any = None,
        json: Any = None,
        timeout: float | None = None,
        allow_redirects: bool = True,
        expected_status: int | Collection[int] | None = None,
        expected_content_type: str | Collection[str] | None = None,
        stream: bool = False,
    ) -> Response:
        attempt = 0

        while True:
            attempt += 1
            self._pace()

            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    data=data,
                    json=json,
                    timeout=self.config.timeout if timeout is None else timeout,
                    allow_redirects=allow_redirects,
                    stream=stream,
                )
            except (ConnectionError, Timeout, ChunkedEncodingError, ContentDecodingError):
                self._last_request_at = self._clock()
                if attempt > self._retry_policy.retries + 1:
                    raise
                sleep_for(retry_delay(attempt, self._retry_policy), "retry", sleeper=self._sleep)
                continue

            self._last_request_at = self._clock()

            if should_retry_status(response.status_code, self._retry_policy):
                if attempt > self._retry_policy.retries + 1:
                    break
                delay = self.config.sleep_429 if response.status_code == 429 else retry_delay(attempt, self._retry_policy)
                sleep_for(delay, "429" if response.status_code == 429 else "retry", sleeper=self._sleep)
                continue

            break

        if not _status_matches(response.status_code, expected_status):
            raise ResponseValidationError(
                f"Unexpected HTTP status {response.status_code} for {response.url}"
            )

        if not _content_type_matches(response.headers.get("Content-Type"), expected_content_type):
            raise ResponseValidationError(
                f"Unexpected content type {response.headers.get('Content-Type')!r} for {response.url}"
            )

        return response

    def request_text(self, url: str, **kwargs: Any) -> str:
        response = self.request(url, **kwargs)
        if response.encoding is None:
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def request_json(self, url: str, **kwargs: Any) -> Any:
        response = self.request(url, expected_content_type=("json",), **kwargs)
        return response.json()

    def request_bytes(self, url: str, **kwargs: Any) -> bytes:
        response = self.request(url, **kwargs)
        return response.content

    def challenge(self, response: Response) -> str | None:
        return detect_challenge(response)
