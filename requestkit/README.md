# requestkit

`requestkit` is the request/session layer for this workspace.

It is meant for "make this request like a sane browser-backed tool would," not full scraping automation.

## Current scope

- browser-like session setup
- retries and backoff
- request pacing
- `429` handling
- challenge detection
- redacted diagnostics
- `cookies.txt` interoperability

Recommended CLI path from the workspace root:

```bash
uv run dl requestkit --help
```

Direct package invocation also works:

```bash
uv run --package requestkit requestkit --help
```

## CLI

Current commands:

- `requestkit get URL`
- `requestkit dump URL`

Shared flags:

- `--browser`
- `--user-agent`
- `--referer`
- `--proxy`
- `--cookies`
- `--timeout`
- `--retries`
- `--sleep-request`
- `--sleep-429`
- `--json`

Examples:

```bash
uv run dl requestkit get https://example.com --browser chrome
```

```bash
uv run dl requestkit dump https://example.com --browser firefox --json
```

Use `dump` when you want a redacted request/response exchange, challenge labeling, and headers/body visibility.

## Library

Build a client and fetch JSON:

```python
from requestkit import RequestClient, SessionConfig

client = RequestClient(
    SessionConfig(
        browser="chrome",
        cookies="cookies.txt",
        retries=2,
        sleep_429=5.0,
    )
)

data = client.request_json("https://example.com/api")
print(data)
```

Useful public imports:

```python
from requestkit import (
    RequestClient,
    ResponseValidationError,
    RetryPolicy,
    SessionConfig,
    build_session,
    detect_challenge,
    format_exchange,
    redact_header_value,
    redact_headers,
    summarize_response,
)
```

## Notes

- Challenge detection currently labels common Cloudflare and DDoS-Guard challenge responses. It does not solve them.
- `requestkit` loads Netscape `cookies.txt`; browser extraction itself stays in `cookiekit`.
- The root `dl` wrapper is only a dispatcher. The actual CLI surface still lives in `requestkit`.
