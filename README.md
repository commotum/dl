# Practical Download Tooling

This repo is a personal workspace for three small tools plus one top-level wrapper:

- `cookiekit`: export `cookies.txt` from a browser where you are already logged in
- `requestkit`: make requests with browser-like headers, retries, pacing, `429` handling, and redacted dumps
- `downloadkit`: download a URL to disk with resume, fallback URLs, and binary-vs-HTML validation
- `dl`: wrapper CLI that dispatches to the three package CLIs

## Quick start

Show the wrapper help:

```bash
uv run dl --help
```

Export cookies from a logged-in browser:

```bash
uv run dl cookiekit export-browser \
  --browser chrome \
  --domain .github.com \
  --output github-cookies.txt
```

Inspect a request with browser-like headers:

```bash
uv run dl requestkit dump \
  https://example.com \
  --browser chrome \
  --json
```

Download a file using those cookies:

```bash
uv run dl downloadkit fetch \
  https://example.com/file.bin \
  -o file.bin \
  --cookies github-cookies.txt \
  --json
```

## Principles

### 1. Prefer real browser state over scripted login

If the user is already logged in, reuse that session instead of reimplementing login flows.

### 2. Separate cookies, requests, and downloads

Cookie extraction, request/session behavior, and file transfer are different concerns with different failure modes. They stay split here on purpose.

### 3. Optimize for ordinary failure modes

The tools focus on the things that usually break naive workflows:

- wrong browser profile
- stale or missing cookies
- bad headers or referers
- `429` responses
- challenge pages returned as HTML
- interrupted downloads
- expired or flaky media URLs

### 4. Keep the shared core generic

The reusable parts are:

- browser-like headers
- retries and pacing
- cookie loading
- challenge detection
- fallback URLs
- resume support

Site-specific hacks belong outside the shared core.

### 5. Small CLIs, small libraries

Each package should work both as:

- a short CLI
- a narrow Python library

The wrapper CLI is the shortest path:

- `uv run dl cookiekit ...`
- `uv run dl requestkit ...`
- `uv run dl downloadkit ...`

### 6. Be explicit

The tools favor visible behavior over hidden magic:

- explicit profile/domain selection
- explicit retry and timeout settings
- visible output paths
- JSON or readable text output

### 7. Redact secrets

Diagnostics should help debug failures without leaking cookies or auth headers.

### 8. Personal tools first

This repo is for practical personal workflows, not for building a maximal framework.

## Current state

- `cookiekit` is usable now
- `requestkit` v1 is usable now
- `downloadkit` v1 is usable now
- `dl` wrapper is usable now

## Workspace map

- `cookiekit/`
- `requestkit/`
- `downloadkit/`
- `gallery-dl/`
- `building-clis-uv-summary.md`

## Related docs

- [`cookiekit/README.md`](cookiekit/README.md)
- [`requestkit/README.md`](requestkit/README.md)
- [`downloadkit/README.md`](downloadkit/README.md)
- [`building-clis-uv-summary.md`](building-clis-uv-summary.md)
- [`cookiekit/docs/release.md`](cookiekit/docs/release.md)
