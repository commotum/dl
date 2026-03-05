"""Standalone cookie management toolkit."""

from .checks import CheckResult, check_required_cookies
from .cookiestxt import dumps_cookies_txt, load_cookies_txt, save_cookies_txt
from .spec import BrowserSpec, parse_browser_spec

__all__ = [
    "BrowserSpec",
    "CheckResult",
    "check_required_cookies",
    "dumps_cookies_txt",
    "load_cookies_txt",
    "parse_browser_spec",
    "save_cookies_txt",
]

__version__ = "0.1.0"
