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

- [ ] Create `requestkit/pyproject.toml`
- [ ] Add `requestkit` to the uv workspace members in the root [pyproject.toml](/home/jake/Developer/dl/pyproject.toml)
- [ ] Start with these modules: `session.py`, `retry.py`, `ratelimit.py`, `challenge.py`, `diagnostics.py`, `cli.py`

## V1 library tasks

- [ ] Define a simple `SessionConfig` for browser preset, user-agent, referer, proxy, timeout, retries, `sleep-request`, and `sleep-429`
- [ ] Implement a session builder with browser-like header presets
- [ ] Implement retry/backoff helpers
- [ ] Implement `wait()` / `sleep()` helpers
- [ ] Implement challenge detection for common response patterns
- [ ] Implement redacted request/response dump helpers
- [ ] Support loading cookies from Netscape `cookies.txt`
- [ ] Add response helpers: `request_json()`, `request_text()`, `request_bytes()`
- [ ] Support simple validation hooks for expected content-type and status

## V1 CLI tasks

- [ ] Define the first CLI surface: `requestkit get URL`, `requestkit dump URL`
- [ ] Add a root-level wrapper command in the parent `dl` folder
- [ ] Support `--browser`, `--user-agent`, `--referer`, `--proxy`, `--cookies`, `--timeout`, `--retries`, `--sleep-request`, `--sleep-429`, and `--json`
- [ ] Make output straightforward for both shell use and AI-agent use

## Quality

- [ ] Add unit tests for retry policy behavior
- [ ] Add unit tests for challenge detection
- [ ] Add integration tests against a local HTTP fixture server
- [ ] Verify cookie import/export interop with `cookiekit`
