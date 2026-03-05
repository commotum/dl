"""Standalone cookie management toolkit."""

from .checks import CheckResult, check_required_cookies
from .browser import load_browser_cookies
from .cookiestxt import dumps_cookies_txt, load_cookies_txt, save_cookies_txt
from .selectors import load_rotate_index, save_rotate_index, select_source
from .spec import BrowserSpec, parse_browser_spec
from .sources import CookieSource, LoadedCookies, load_source, parse_source, resolve_update_target

__all__ = [
    "BrowserSpec",
    "CheckResult",
    "CookieSource",
    "LoadedCookies",
    "check_required_cookies",
    "dumps_cookies_txt",
    "load_browser_cookies",
    "load_rotate_index",
    "load_source",
    "load_cookies_txt",
    "parse_browser_spec",
    "parse_source",
    "resolve_update_target",
    "save_rotate_index",
    "save_cookies_txt",
    "select_source",
]

__version__ = "0.1.0"
