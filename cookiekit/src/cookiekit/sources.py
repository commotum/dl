"""Cookie source parsing and loading."""

from __future__ import annotations

from dataclasses import dataclass
from http.cookiejar import Cookie

from .browser import load_browser_cookies
from .cookiestxt import load_cookies_txt
from .spec import parse_browser_spec


@dataclass(frozen=True)
class CookieSource:
    kind: str
    value: str


@dataclass(frozen=True)
class LoadedCookies:
    source: CookieSource
    cookies: tuple[Cookie, ...]
    update_candidate: str | None


def parse_source(value: str) -> CookieSource:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty source")

    if raw.startswith("browser:"):
        spec_value = raw.split(":", 1)[1].strip()
        # Validate now; extraction itself lands in Phase 3.
        parse_browser_spec(spec_value)
        return CookieSource(kind="browser", value=spec_value)

    return CookieSource(kind="file", value=raw)


def load_source(source: CookieSource) -> LoadedCookies:
    if source.kind == "file":
        cookies = tuple(load_cookies_txt(source.value))
        return LoadedCookies(
            source=source,
            cookies=cookies,
            update_candidate=source.value,
        )

    if source.kind == "browser":
        spec = parse_browser_spec(source.value)
        cookies = tuple(load_browser_cookies(spec))
        return LoadedCookies(
            source=source,
            cookies=cookies,
            update_candidate=None,
        )

    raise ValueError(f"unsupported source type: {source.kind!r}")


def resolve_update_target(update_value: str, loaded: LoadedCookies) -> str | None:
    normalized = (update_value or "").strip().lower()

    if normalized in {"off", "false", "0", "no"}:
        return None

    if normalized in {"auto", "true", "1", "yes"}:
        return loaded.update_candidate

    return update_value
