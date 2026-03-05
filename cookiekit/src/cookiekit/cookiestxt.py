"""Netscape/Mozilla cookies.txt parsing and writing."""

from __future__ import annotations

from http.cookiejar import Cookie
from pathlib import Path
from typing import Iterable

from .persist import atomic_write_text

COOKIESTXT_HEADER = "# Netscape HTTP Cookie File"


def _parse_bool(value: str) -> bool:
    return value.strip().upper() in {"TRUE", "1", "YES"}


def _parse_expires(value: str) -> int | None:
    raw = value.strip()
    if not raw or raw == "0":
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _make_cookie(
    domain: str,
    path: str,
    secure: bool,
    expires: int | None,
    name: str,
    value: str,
) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=bool(domain),
        domain_initial_dot=domain.startswith("."),
        path=path,
        path_specified=bool(path),
        secure=secure,
        expires=expires,
        discard=expires is None,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


def load_cookies_txt(path: str | Path) -> list[Cookie]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return load_cookies_txt_lines(handle)


def load_cookies_txt_lines(lines: Iterable[str]) -> list[Cookie]:
    cookies: list[Cookie] = []

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            continue

        # Some exports use a prefix for HttpOnly cookies.
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_") :]

        if line.startswith("#") or line.startswith("$"):
            continue

        parts = line.split("\t")
        if len(parts) == 6:
            # Tolerate value-only form without cookie name.
            parts.insert(5, "")
        if len(parts) != 7:
            continue

        domain, _include_subdomains, path, secure_raw, expires_raw, name, value = parts
        secure = _parse_bool(secure_raw)
        expires = _parse_expires(expires_raw)
        cookies.append(
            _make_cookie(
                domain=domain,
                path=path,
                secure=secure,
                expires=expires,
                name=name,
                value=value,
            )
        )

    return cookies


def cookie_to_cookiestxt_line(cookie: Cookie) -> str | None:
    # Domainless cookies cannot be represented in cookies.txt.
    if not cookie.domain:
        return None

    include_subdomains = "TRUE" if cookie.domain_initial_dot else "FALSE"
    secure = "TRUE" if cookie.secure else "FALSE"
    expires = "0" if cookie.expires is None else str(int(cookie.expires))
    name = cookie.name or ""
    value = cookie.value or ""

    return "\t".join(
        [cookie.domain, include_subdomains, cookie.path, secure, expires, name, value]
    )


def dumps_cookies_txt(cookies: Iterable[Cookie]) -> str:
    lines = [COOKIESTXT_HEADER]
    for cookie in cookies:
        line = cookie_to_cookiestxt_line(cookie)
        if line is not None:
            lines.append(line)
    return "\n".join(lines) + "\n"


def save_cookies_txt(path: str | Path, cookies: Iterable[Cookie], atomic: bool = True) -> None:
    output = dumps_cookies_txt(cookies)
    destination = Path(path)
    if atomic:
        atomic_write_text(destination, output, encoding="utf-8")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output, encoding="utf-8")
