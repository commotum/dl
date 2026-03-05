"""Browser cookie extraction for Firefox/Chromium/WebKit."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import struct
import tempfile
from contextlib import contextmanager
from http.cookiejar import Cookie
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from .spec import (
    BrowserSpec,
    SUPPORTED_BROWSERS_CHROMIUM,
    SUPPORTED_BROWSERS_FIREFOX,
    SUPPORTED_BROWSERS_WEBKIT,
)

SUPPORTED_KEYRINGS = {"kwallet", "gnomekeyring", "basictext"}


def load_browser_cookies(spec: BrowserSpec) -> list[Cookie]:
    _validate_keyring(spec)

    if spec.browser in SUPPORTED_BROWSERS_FIREFOX:
        return load_firefox_cookies(spec)
    if spec.browser in SUPPORTED_BROWSERS_CHROMIUM:
        return load_chromium_cookies(spec)
    if spec.browser in SUPPORTED_BROWSERS_WEBKIT:
        return load_webkit_cookies(spec)

    raise ValueError(f"unsupported browser {spec.browser!r}")


def _validate_keyring(spec: BrowserSpec) -> None:
    if not spec.keyring:
        return
    keyring = spec.keyring.lower()

    if spec.browser not in SUPPORTED_BROWSERS_CHROMIUM:
        raise ValueError(
            f"keyring override is only supported for chromium browsers; got {spec.browser!r}"
        )
    if keyring not in SUPPORTED_KEYRINGS:
        supported = ", ".join(sorted(SUPPORTED_KEYRINGS))
        raise ValueError(f"unsupported keyring {spec.keyring!r}; expected one of: {supported}")


@contextmanager
def sqlite_cookie_db(path: str | Path):
    db_path = Path(path).expanduser().resolve()
    conn: sqlite3.Connection | None = None
    tmp_dir: str | None = None
    try:
        uri = sqlite_path_to_uri(db_path)
        try:
            conn = sqlite3.connect(uri, uri=True, isolation_level=None, check_same_thread=False)
            yield conn
            return
        except Exception:
            pass

        tmp_dir = tempfile.mkdtemp(prefix="cookiekit-")
        copied = Path(tmp_dir) / db_path.name
        shutil.copyfile(db_path, copied)
        conn = sqlite3.connect(str(copied), isolation_level=None, check_same_thread=False)
        yield conn
    finally:
        if conn is not None:
            conn.close()
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def sqlite_path_to_uri(path: Path) -> str:
    absolute = str(path.resolve())
    if os.name == "nt":
        absolute = absolute.replace("\\", "/")
        if not absolute.startswith("/"):
            absolute = "/" + absolute
    escaped = quote(absolute, safe="/:")
    return f"file:{escaped}?mode=ro&immutable=1"


def _looks_like_path(value: str) -> bool:
    return value.startswith("/") or value.startswith("./") or value.startswith("../") or value.startswith("~")


def _find_latest_file(search_roots: Iterable[str | Path], filename: str) -> Path | None:
    candidates: list[Path] = []
    for root in search_roots:
        root_path = Path(root).expanduser()
        if root_path.is_file():
            if root_path.name == filename:
                candidates.append(root_path)
            continue
        if not root_path.exists():
            continue
        direct = root_path / filename
        if direct.is_file():
            candidates.append(direct)
        candidates.extend(path for path in root_path.rglob(filename) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _domain_condition(column: str, domain: str | None) -> tuple[str | None, tuple[str, ...]]:
    if not domain:
        return None, ()
    if domain.startswith("."):
        return f"{column} == ? OR {column} LIKE ?", (domain[1:], "%" + domain)
    return f"{column} == ? OR {column} == ?", (domain, "." + domain)


def _cookie(
    *,
    name: str,
    value: str,
    domain: str,
    path: str,
    secure: bool,
    expires: int | None,
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


def load_firefox_cookies(spec: BrowserSpec) -> list[Cookie]:
    db_path = resolve_firefox_cookie_db(spec.browser, spec.profile)
    container = spec.container or "none"
    container_filter, container_params = _firefox_container_condition(db_path, container)
    domain_filter, domain_params = _domain_condition("host", spec.domain)

    sql = "SELECT name, value, host, path, isSecure, expiry FROM moz_cookies"
    conditions: list[str] = []
    params: list[str] = []

    if container_filter:
        conditions.append(container_filter)
        params.extend(container_params)
    if domain_filter:
        conditions.append(domain_filter)
        params.extend(domain_params)
    if conditions:
        sql += " WHERE (" + ") AND (".join(conditions) + ")"

    cookies: list[Cookie] = []
    with sqlite_cookie_db(db_path) as conn:
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.OperationalError as exc:
            if "originAttributes" not in str(exc):
                raise
            # Older/variant schemas may omit originAttributes.
            if container not in {"none", "all"}:
                raise ValueError("firefox container filtering is unavailable for this profile schema")
            sql_without_container = "SELECT name, value, host, path, isSecure, expiry FROM moz_cookies"
            if domain_filter:
                sql_without_container += " WHERE (" + domain_filter + ")"
                rows = conn.execute(sql_without_container, domain_params).fetchall()
            else:
                rows = conn.execute(sql_without_container).fetchall()

    for name, value, host, path, is_secure, expiry in rows:
        cookies.append(
            _cookie(
                name=str(name),
                value=str(value),
                domain=str(host),
                path=str(path),
                secure=bool(is_secure),
                expires=int(expiry) if expiry else None,
            )
        )
    return cookies


def _firefox_container_condition(db_path: Path, container: str) -> tuple[str | None, tuple[str, ...]]:
    if container == "all":
        return None, ()
    if container == "none":
        return "NOT INSTR(originAttributes,'userContextId=')", ()

    identities = _load_firefox_containers(db_path)
    wanted_id: int | None = None
    for identity in identities:
        name = str(identity.get("name", ""))
        l10n = str(identity.get("l10nID", ""))
        label = _extract_firefox_l10n_label(l10n)
        if container in {name, label}:
            wanted_id = int(identity["userContextId"])
            break
    if wanted_id is None:
        raise ValueError(f"unable to find Firefox container {container!r}")

    prefix = f"%userContextId={wanted_id}"
    return "originAttributes LIKE ? OR originAttributes LIKE ?", (prefix, prefix + "&%")


def _extract_firefox_l10n_label(value: str) -> str:
    # e.g. "userContext2.label"
    if value.startswith("userContext") and value.endswith(".label"):
        return value[len("userContext") : -len(".label")]
    return value


def _load_firefox_containers(db_path: Path) -> list[dict]:
    containers_path = db_path.parent / "containers.json"
    if not containers_path.exists():
        return []
    data = json.loads(containers_path.read_text(encoding="utf-8"))
    identities = data.get("identities", [])
    if not isinstance(identities, list):
        return []
    return [item for item in identities if isinstance(item, dict)]


def resolve_firefox_cookie_db(browser: str, profile: str | None) -> Path:
    search_roots: list[str | Path] = []
    if profile:
        if _looks_like_path(profile):
            search_roots.append(profile)
        else:
            search_roots.extend(str(Path(root) / profile) for root in firefox_profile_roots(browser))
    else:
        search_roots.extend(firefox_profile_roots(browser))

    path = _find_latest_file(search_roots, "cookies.sqlite")
    if path is None:
        raise FileNotFoundError(f"unable to find {browser} cookies.sqlite")
    return path


def firefox_profile_roots(browser: str) -> tuple[str, ...]:
    if sys_platform() in {"win32", "cygwin"}:
        appdata = os.path.expandvars("%APPDATA%")
        mapping = {
            "firefox": (rf"{appdata}\Mozilla\Firefox\Profiles",),
            "librewolf": (rf"{appdata}\librewolf\Profiles",),
            "zen": (rf"{appdata}\zen\Profiles",),
            "floorp": (rf"{appdata}\Floorp\Profiles",),
        }
        return mapping[browser]
    if sys_platform() == "darwin":
        appdata = os.path.expanduser("~/Library/Application Support")
        mapping = {
            "firefox": (f"{appdata}/Firefox/Profiles",),
            "librewolf": (f"{appdata}/librewolf/Profiles",),
            "zen": (f"{appdata}/zen/Profiles",),
            "floorp": (f"{appdata}/Floorp/Profiles",),
        }
        return mapping[browser]

    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    home = os.path.expanduser("~")
    mapping = {
        "firefox": (
            f"{config}/mozilla/firefox",
            f"{home}/.mozilla/firefox",
            f"{home}/.var/app/org.mozilla.firefox/config/mozilla/firefox",
            f"{home}/.var/app/org.mozilla.firefox/.mozilla/firefox",
            f"{home}/snap/firefox/common/.mozilla/firefox",
        ),
        "librewolf": (
            f"{home}/.librewolf",
            f"{home}/.var/app/io.gitlab.librewolf-community/.librewolf",
        ),
        "zen": (f"{home}/.zen",),
        "floorp": (f"{home}/.floorp",),
    }
    return mapping[browser]


def load_chromium_cookies(spec: BrowserSpec) -> list[Cookie]:
    db_path = resolve_chromium_cookie_db(spec.browser, spec.profile)
    domain_filter, domain_params = _domain_condition("host_key", spec.domain)

    sql = "SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure FROM cookies"
    if domain_filter:
        sql += " WHERE (" + domain_filter + ")"

    cookies: list[Cookie] = []
    with sqlite_cookie_db(db_path) as conn:
        conn.text_factory = bytes
        try:
            rows = conn.execute(sql, domain_params).fetchall()
        except sqlite3.OperationalError:
            sql = sql.replace("is_secure", "secure")
            rows = conn.execute(sql, domain_params).fetchall()

    for host_key, name, value, encrypted_value, path, expires_utc, is_secure in rows:
        host = _decode_sql_value(host_key)
        cookie_name = _decode_sql_value(name)
        plain_value = _decode_sql_value(value)
        encrypted_blob = encrypted_value or b""

        if not plain_value and encrypted_blob:
            # Phase 4 adds decryption support.
            continue

        expires = _chromium_epoch_to_unix(expires_utc)
        cookies.append(
            _cookie(
                name=cookie_name,
                value=plain_value,
                domain=host,
                path=_decode_sql_value(path),
                secure=bool(is_secure),
                expires=expires,
            )
        )

    return cookies


def _decode_sql_value(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None:
        return ""
    return str(value)


def _chromium_epoch_to_unix(expires_utc: object) -> int | None:
    if not expires_utc:
        return None
    try:
        value = int(expires_utc)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    # microseconds since 1601-01-01 -> seconds since 1970-01-01
    return value // 1_000_000 - 11_644_473_600


def resolve_chromium_cookie_db(browser: str, profile: str | None) -> Path:
    roots = chromium_profile_roots(browser)
    search_roots: list[str | Path] = []

    if profile:
        if _looks_like_path(profile):
            search_roots.append(profile)
        else:
            search_roots.extend(str(Path(root) / profile) for root in roots)
    else:
        search_roots.extend(roots)

    path = _find_latest_file(search_roots, "Cookies")
    if path is None:
        raise FileNotFoundError(f"unable to find {browser} Cookies database")
    return path


def chromium_profile_roots(browser: str) -> tuple[str, ...]:
    if sys_platform() in {"win32", "cygwin"}:
        local = os.path.expandvars("%LOCALAPPDATA%")
        roaming = os.path.expandvars("%APPDATA%")
        mapping = {
            "brave": (rf"{local}\BraveSoftware\Brave-Browser\User Data",),
            "chrome": (rf"{local}\Google\Chrome\User Data",),
            "chromium": (rf"{local}\Chromium\User Data",),
            "edge": (rf"{local}\Microsoft\Edge\User Data",),
            "opera": (rf"{roaming}\Opera Software\Opera Stable",),
            "thorium": (rf"{local}\Thorium\User Data",),
            "vivaldi": (rf"{local}\Vivaldi\User Data",),
        }
        return mapping[browser]
    if sys_platform() == "darwin":
        appdata = os.path.expanduser("~/Library/Application Support")
        mapping = {
            "brave": (f"{appdata}/BraveSoftware/Brave-Browser",),
            "chrome": (f"{appdata}/Google/Chrome",),
            "chromium": (f"{appdata}/Chromium",),
            "edge": (f"{appdata}/Microsoft Edge",),
            "opera": (f"{appdata}/com.operasoftware.Opera",),
            "thorium": (f"{appdata}/Thorium",),
            "vivaldi": (f"{appdata}/Vivaldi",),
        }
        return mapping[browser]

    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    mapping = {
        "brave": (f"{config}/BraveSoftware/Brave-Browser",),
        "chrome": (f"{config}/google-chrome",),
        "chromium": (f"{config}/chromium",),
        "edge": (f"{config}/microsoft-edge",),
        "opera": (f"{config}/opera",),
        "thorium": (f"{config}/Thorium",),
        "vivaldi": (f"{config}/vivaldi",),
    }
    return mapping[browser]


def load_webkit_cookies(spec: BrowserSpec) -> list[Cookie]:
    binarycookies_path = resolve_webkit_binarycookies(spec.browser, spec.profile)
    data = binarycookies_path.read_bytes()
    return parse_webkit_binarycookies(data, domain=spec.domain)


def resolve_webkit_binarycookies(browser: str, profile: str | None) -> Path:
    if profile:
        roots: list[str | Path] = [profile]
        path = _find_latest_file(roots, "Cookies.binarycookies")
        if path is not None:
            return path
        binary = _find_latest_binarycookies(roots)
        if binary is not None:
            return binary
    else:
        defaults = webkit_default_paths(browser)
        for candidate in defaults:
            path = Path(candidate).expanduser()
            if path.is_file():
                return path

    raise FileNotFoundError(f"unable to find {browser} binary cookies database")


def _find_latest_binarycookies(roots: Iterable[str | Path]) -> Path | None:
    candidates: list[Path] = []
    for root in roots:
        root_path = Path(root).expanduser()
        if root_path.is_file() and root_path.suffix == ".binarycookies":
            candidates.append(root_path)
            continue
        if not root_path.exists():
            continue
        candidates.extend(path for path in root_path.rglob("*.binarycookies") if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def webkit_default_paths(browser: str) -> tuple[str, ...]:
    if browser == "safari":
        return (
            "~/Library/Cookies/Cookies.binarycookies",
            "~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies",
        )
    if browser == "orion":
        return ("~/Library/HTTPStorages/com.kagi.kagimacOS.binarycookies",)
    raise ValueError(f"unsupported webkit browser: {browser}")


def parse_webkit_binarycookies(data: bytes, domain: str | None = None) -> list[Cookie]:
    if len(data) < 8 or data[:4] != b"cook":
        raise ValueError("invalid WebKit binarycookies signature")

    page_count = struct.unpack(">I", data[4:8])[0]
    offset = 8
    page_sizes: list[int] = []
    for _ in range(page_count):
        if offset + 4 > len(data):
            raise ValueError("invalid WebKit binarycookies header")
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        page_sizes.append(size)
        offset += 4

    cookies: list[Cookie] = []
    for page_size in page_sizes:
        page = data[offset : offset + page_size]
        offset += page_size
        cookies.extend(_parse_webkit_page(page, domain=domain))
    return cookies


def _parse_webkit_page(page: bytes, domain: str | None) -> list[Cookie]:
    if len(page) < 8 or page[:4] != b"\x00\x00\x01\x00":
        return []
    cookie_count = struct.unpack("<I", page[4:8])[0]
    header_end = 8 + 4 * cookie_count
    if len(page) < header_end:
        return []

    offsets = [
        struct.unpack("<I", page[8 + i * 4 : 12 + i * 4])[0]
        for i in range(cookie_count)
    ]

    cookies: list[Cookie] = []
    for record_offset in offsets:
        if record_offset + 4 > len(page):
            continue
        record_size = struct.unpack("<I", page[record_offset : record_offset + 4])[0]
        record = page[record_offset : record_offset + record_size]
        cookie = _parse_webkit_record(record, domain=domain)
        if cookie is not None:
            cookies.append(cookie)
    return cookies


def _parse_webkit_record(record: bytes, domain: str | None) -> Cookie | None:
    if len(record) < 56:
        return None

    flags = struct.unpack("<I", record[8:12])[0]
    domain_offset = struct.unpack("<I", record[16:20])[0]
    name_offset = struct.unpack("<I", record[20:24])[0]
    path_offset = struct.unpack("<I", record[24:28])[0]
    value_offset = struct.unpack("<I", record[28:32])[0]
    expires_raw = struct.unpack("<d", record[40:48])[0]

    cookie_domain = _read_cstring(record, domain_offset)
    if cookie_domain is None:
        return None
    if not _cookie_domain_matches(cookie_domain, domain):
        return None

    name = _read_cstring(record, name_offset)
    cookie_path = _read_cstring(record, path_offset)
    value = _read_cstring(record, value_offset)
    if name is None or cookie_path is None or value is None:
        return None

    return _cookie(
        name=name,
        value=value,
        domain=cookie_domain,
        path=cookie_path,
        secure=bool(flags & 0x0001),
        expires=_mac_absolute_to_unix(expires_raw),
    )


def _read_cstring(data: bytes, offset: int) -> str | None:
    if offset < 0 or offset >= len(data):
        return None
    end = data.find(b"\x00", offset)
    if end == -1:
        return None
    return data[offset:end].decode("utf-8", errors="replace")


def _cookie_domain_matches(cookie_domain: str, wanted_domain: str | None) -> bool:
    if not wanted_domain:
        return True
    if wanted_domain.startswith("."):
        return cookie_domain == wanted_domain[1:] or cookie_domain.endswith(wanted_domain)
    return cookie_domain in {wanted_domain, "." + wanted_domain}


def _mac_absolute_to_unix(value: float) -> int | None:
    if not value:
        return None
    unix = int(value + 978307200)
    return unix if unix > 0 else None


def sys_platform() -> str:
    return os.sys.platform
