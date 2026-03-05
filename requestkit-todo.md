# requestkit TODO

## Goal

Build `requestkit` as the small shared HTTP/session layer for personal use.

It should cover just the reusable request behavior that sits between `cookiekit` and any future site-specific code:

- browser-like session setup
- retries and backoff
- request pacing
- `429` handling
- challenge detection
- cookies.txt interoperability
- redacted diagnostics

## Package shape

- [x] Create `requestkit/pyproject.toml`
- [x] Add `requestkit` to the uv workspace members in the root [pyproject.toml](/home/jake/Developer/dl/pyproject.toml)
- [x] Start with these modules: `session.py`, `retry.py`, `ratelimit.py`, `challenge.py`, `diagnostics.py`, `cli.py`

## V1 library tasks

- [x] Define a simple `SessionConfig` for browser preset, user-agent, referer, proxy, timeout, retries, `sleep-request`, and `sleep-429`
- [x] Implement a session builder with browser-like header presets
- [x] Implement retry/backoff helpers
- [x] Implement `wait()` / `sleep()` helpers
- [x] Implement challenge detection for common response patterns
- [x] Implement redacted request/response dump helpers
- [x] Support loading cookies from Netscape `cookies.txt`
- [x] Add response helpers: `request_json()`, `request_text()`, `request_bytes()`
- [x] Support simple validation hooks for expected content-type and status

## V1 CLI tasks

- [x] Define the first CLI surface: `requestkit get URL`, `requestkit dump URL`
- [x] Add a root-level wrapper command in the parent `dl` folder
- [x] Support `--browser`, `--user-agent`, `--referer`, `--proxy`, `--cookies`, `--timeout`, `--retries`, `--sleep-request`, `--sleep-429`, and `--json`
- [x] Make output straightforward for both shell use and AI-agent use

## Quality

- [ ] Add a more focused unit test for retry delay / retry policy calculations
- [x] Add unit tests for challenge detection
- [x] Add integration tests against a local HTTP fixture server
- [x] Verify cookie import/export interop with `cookiekit`
