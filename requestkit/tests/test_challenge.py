from __future__ import annotations

import requests

from requestkit import detect_challenge


def test_detects_cloudflare_challenge(http_server):
    response = requests.get(http_server["base_url"] + "/challenge", timeout=5)
    assert detect_challenge(response) == "Cloudflare challenge"
