"""Cookie health checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http.cookiejar import Cookie
from typing import Iterable


@dataclass(frozen=True)
class CheckResult:
    required: tuple[str, ...]
    missing: tuple[str, ...]
    expired: tuple[str, ...]
    expiring_soon: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.expired


def _normalize_domain(domain: str | None) -> str | None:
    if domain is None:
        return None
    cleaned = domain.strip().lower().lstrip(".")
    return cleaned or None


def _domain_matches(cookie_domain: str | None, target_domain: str, allow_subdomains: bool) -> bool:
    normalized_cookie_domain = _normalize_domain(cookie_domain)
    if normalized_cookie_domain is None:
        return False
    if normalized_cookie_domain == target_domain:
        return True
    if allow_subdomains and normalized_cookie_domain.endswith(f".{target_domain}"):
        return True
    return False


def _select_cookie(
    cookies: Iterable[Cookie],
    name: str,
    domain: str | None,
    allow_subdomains: bool,
) -> Cookie | None:
    target = _normalize_domain(domain)
    for cookie in cookies:
        if cookie.name != name:
            continue
        if target is None:
            return cookie
        if _domain_matches(cookie.domain, target, allow_subdomains):
            return cookie
    return None


def check_required_cookies(
    cookies: Iterable[Cookie],
    required_names: Iterable[str],
    *,
    domain: str | None = None,
    allow_subdomains: bool = False,
    expiring_soon_seconds: int = 24 * 60 * 60,
    now: int | None = None,
) -> CheckResult:
    if now is None:
        now = int(datetime.now(tz=timezone.utc).timestamp())

    required = tuple(required_names)
    missing: list[str] = []
    expired: list[str] = []
    expiring_soon: list[str] = []

    cookie_list = list(cookies)
    for name in required:
        cookie = _select_cookie(cookie_list, name, domain, allow_subdomains)
        if cookie is None:
            missing.append(name)
            continue
        if cookie.expires is None:
            continue
        if cookie.expires <= now:
            expired.append(name)
            continue
        if cookie.expires - now < expiring_soon_seconds:
            expiring_soon.append(name)

    return CheckResult(
        required=required,
        missing=tuple(missing),
        expired=tuple(expired),
        expiring_soon=tuple(expiring_soon),
    )
