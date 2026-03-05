"""Challenge-detection helpers for requestkit."""

from __future__ import annotations

from requests import Response


def detect_challenge(response: Response) -> str | None:
    """Return a short challenge label when the response looks blocked."""

    server = response.headers.get("server", "").lower()
    content = response.content or b""

    if "cloudflare" in server:
        if response.status_code not in (403, 503):
            return None

        mitigated = response.headers.get("cf-mitigated", "")
        if mitigated.lower() == "challenge":
            return "Cloudflare challenge"

        if b"_cf_chl_opt" in content or b"jschl-answer" in content:
            return "Cloudflare challenge"
        if b'name="captcha-bypass"' in content:
            return "Cloudflare CAPTCHA"

    if "ddos-guard" in server:
        if response.status_code == 403 and b"/ddos-guard/js-challenge/" in content:
            return "DDoS-Guard challenge"

    return None
