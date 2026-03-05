"""Browser cookie source specification parsing."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_BROWSERS_CHROMIUM = {
    "brave",
    "chrome",
    "chromium",
    "edge",
    "opera",
    "thorium",
    "vivaldi",
}
SUPPORTED_BROWSERS_FIREFOX = {"firefox", "librewolf", "zen", "floorp"}
SUPPORTED_BROWSERS_WEBKIT = {"safari", "orion"}
SUPPORTED_BROWSERS = (
    SUPPORTED_BROWSERS_CHROMIUM
    | SUPPORTED_BROWSERS_FIREFOX
    | SUPPORTED_BROWSERS_WEBKIT
)


@dataclass(frozen=True)
class BrowserSpec:
    browser: str
    profile: str | None = None
    keyring: str | None = None
    container: str | None = None
    domain: str | None = None


def parse_browser_spec(value: str) -> BrowserSpec:
    """
    Parse:
      BROWSER[/DOMAIN][+KEYRING][:PROFILE][::CONTAINER]
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("browser specification is empty")

    body = raw
    container: str | None = None
    if "::" in body:
        body, container = body.split("::", 1)
        container = container.strip() or None
        if container and "::" in container:
            raise ValueError(f"invalid browser specification: {value!r}")

    profile: str | None = None
    if ":" in body:
        body, profile = body.split(":", 1)
        profile = profile.strip() or None

    keyring: str | None = None
    if "+" in body:
        body, keyring = body.split("+", 1)
        keyring = keyring.strip() or None

    browser = body
    domain: str | None = None
    if "/" in body:
        browser, domain = body.split("/", 1)
        domain = domain.strip() or None

    browser = browser.strip().lower()
    if browser not in SUPPORTED_BROWSERS:
        supported = ", ".join(sorted(SUPPORTED_BROWSERS))
        raise ValueError(f"unsupported browser {browser!r}; expected one of: {supported}")

    return BrowserSpec(
        browser=browser,
        profile=profile,
        keyring=keyring,
        container=container,
        domain=domain,
    )
