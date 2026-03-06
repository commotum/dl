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

The goal here is practical, low-noise downloading: behave like a normal
browser-backed session, make as few mistakes as possible, and avoid leaving an
obvious "naive scraper" footprint.

### 1. Prefer real browser state over scripted login

If you are already logged in, reuse that session instead of rebuilding login
flows or automating forms by default.

### 2. Minimize footprint

Good scraping starts with not being noisy:

- make the fewest requests needed
- reuse cookies and session state
- send sensible headers and referers
- back off on `429`
- avoid pointless retries and probes

### 3. Look browser-backed, not custom

The safest default is usually to look like an ordinary browser-driven request
flow, not a bespoke automation stack.

That means prioritizing:

- browser-like headers
- real cookies
- sane pacing
- consistent referers
- ordinary request patterns

### 4. Treat detection as a failure signal

If a site starts returning login pages, challenge HTML, or other unexpected
responses, stop and inspect the flow instead of trying to brute-force through
it.

The tools should make those failures visible.

### 5. Download carefully

Good downloading is not just "GET and save":

- write atomically
- resume when possible
- reject HTML masquerading as a file
- validate the response before trusting it
- use fallback URLs when the primary one is flaky

### 6. Be explicit and inspectable

These tools should favor visible behavior over hidden magic:

- explicit profile and domain selection
- explicit retry and timeout settings
- visible output paths
- JSON or readable text output
- redacted but useful diagnostics

### 7. Keep the tools composable

`cookiekit`, `requestkit`, and `downloadkit` exist because cookies, requests,
and file transfer are still useful mental buckets.

They do not need perfect boundaries. Share code freely when it makes the
personal workflow simpler.

### 8. Personal utility beats framework purity

This repo is a personal toolbox. If a feature makes day-to-day scraping and
downloading easier, that matters more than maintaining a pristine architecture.

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
