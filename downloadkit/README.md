# downloadkit

`downloadkit` is the file-transfer layer for this workspace.

Current scope:

- atomic file writes
- resume support
- fallback URLs
- response validation
- robust single-file fetches

Current CLI:

- `downloadkit fetch URL -o PATH`

Supported flags today:

- `--cookies`
- `--resume` / `--no-resume`
- `--overwrite`
- `--retry`
- `--timeout`
- `--rate`
- `--header`
- `--fallback`
- `--json`
- `--browser`
- `--user-agent`
- `--referer`
- `--proxy`

Status:

- v1 core is implemented
- it uses `requestkit` for session/request behavior
- the root-level parent `dl` wrapper is still pending
