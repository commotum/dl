# requestkit

`requestkit` is the request/session layer for this workspace.

Current scope:

- browser-like session setup
- retries and backoff
- request pacing
- `429` handling
- challenge detection
- redacted diagnostics
- `cookies.txt` interoperability

Current CLI:

- `requestkit get URL`
- `requestkit dump URL`

Supported flags today:

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

Status:

- v1 core is implemented
- the root-level parent `dl` wrapper is still pending
- more tests and polish can still be added
