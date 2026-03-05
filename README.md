# cookiekit Workspace

Standalone cookie extraction and session-cookie workflow toolkit for downloader agents.

This repository currently focuses on `cookiekit` (library + CLI), with `gallery-dl/` retained as a submodule/reference source.

## What Is Implemented

`cookiekit` currently includes the full V1 feature set:

- Netscape `cookies.txt` compatibility (read/write/round-trip).
- Atomic cookie writes (`.tmp` + replace).
- Browser source spec parsing:
  - `BROWSER[/DOMAIN][+KEYRING][:PROFILE][::CONTAINER]`
- Multi-source cookie loading:
  - file sources
  - browser sources
- Source selection strategies:
  - `first`
  - `random` (seedable)
  - `rotate` (persistent state file)
- Cookie update targeting (`auto`, `off`, or explicit output path).
- Cookie checks:
  - required cookie names
  - optional domain/subdomain scope
  - expired and expiring-soon detection
- Browser extraction support:
  - Firefox family
  - Chromium family
  - WebKit/Safari binarycookies
- Firefox container filtering.
- SQLite lock-safe reads:
  - read-only immutable mode
  - copy fallback when direct lock-safe open is not available
- Chromium encrypted cookie decryption:
  - Linux, macOS, Windows paths
  - per-mode failure/decrypt accounting
- Redacted diagnostics helpers for sensitive values.
- Packaged CLI entrypoint + build/release workflow + CI workflow.

## Repo Layout

- `cookiekit/`: Python package (library + CLI).
- `cookiekit/src/cookiekit/`: implementation modules.
- `cookiekit/tests/`: test suite.
- `cookiekit/docs/release.md`: build/release/smoke-test workflow.
- `cookiekit/CHANGELOG.md`: versioned changes.
- `todo.md`: roadmap and completion status.
- `gallery-dl/`: submodule/reference codebase.

## Quick Start

Prerequisites:
- Python `>=3.10`
- `uv`

Install workspace package:

```bash
uv sync --package cookiekit
```

Run CLI help:

```bash
uv run --package cookiekit cookiekit --help
```

## CLI Guide

Core commands:

```bash
uv run --package cookiekit cookiekit load path/to/cookies.txt
uv run --package cookiekit cookiekit save --input in.txt --output out.txt
uv run --package cookiekit cookiekit check path/to/cookies.txt --require sessionid
uv run --package cookiekit cookiekit parse-spec "firefox/.example.com:default-release::Work"
uv run --package cookiekit cookiekit sync --source a.txt --source b.txt --select rotate
uv run --package cookiekit cookiekit noop --source browser:chrome/.example.com+gnomekeyring:Default
```

### `sync` / `noop` Source Flow

`noop` is an alias of `sync`.

Use one or more `--source` values:
- file source: `cookies.txt`
- browser source: `browser:<SPEC>`

Selection mode:
- `--select first` (default)
- `--select random --random-seed 123`
- `--select rotate --rotate-state-file .cookiekit.rotate-state.json`

Persistence behavior:
- `--cookies-update auto`: update only if selected source is a file
- `--cookies-update off`: no write-back
- `--cookies-update /path/to/cookies.txt`: always write to explicit path

Example:

```bash
uv run --package cookiekit cookiekit sync \
  --source cookies-primary.txt \
  --source browser:firefox/.example.com:default-release::Work \
  --source browser:chrome/.example.com+kwallet:Default \
  --select rotate \
  --rotate-state-file .cookiekit.rotate-state.json \
  --cookies-update auto
```

## Browser Spec and Extraction

Browser spec format:

```text
browser:<BROWSER[/DOMAIN][+KEYRING][:PROFILE][::CONTAINER]>
```

Examples:

```text
browser:firefox/.example.com:default-release::Work
browser:chrome/.example.com+gnomekeyring:Default
browser:chrome/.example.com+kwallet:Default
browser:safari/.example.com
```

Notes:
- `+KEYRING` is Chromium-only (`kwallet`, `gnomekeyring`, `basictext`).
- `::CONTAINER` is Firefox container filtering.
- Domain filters are applied during browser DB queries.

## Library Usage

Stable V1 exports are re-exported from `cookiekit`:

```python
from cookiekit import (
    BrowserSpec,
    CheckResult,
    CookieSource,
    LoadedCookies,
    check_required_cookies,
    dumps_cookies_txt,
    load_browser_cookies,
    load_cookies_txt,
    parse_browser_spec,
    parse_source,
    load_source,
    select_source,
    resolve_update_target,
    save_cookies_txt,
    load_rotate_index,
    save_rotate_index,
    redact_header_value,
    redact_headers,
    redact_http_header_lines,
)
```

Minimal example:

```python
from cookiekit import parse_source, load_source, check_required_cookies

source = parse_source("browser:firefox/.example.com:default-release")
loaded = load_source(source)
result = check_required_cookies(loaded.cookies, ["sessionid"], domain=".example.com")
print(result.ok, result.missing, result.expired)
```

## Platform and Decryption Notes

- Chromium encrypted cookie decryption uses `pycryptodome`.
- Linux GNOME keyring support uses `secretstorage`.
- Linux KWallet support uses `kwallet-query`.
- If AES or keyring material is unavailable, cookie decryption failures are counted and reported (instead of crashing).

## Development

Run tests:

```bash
uv run --package cookiekit --group dev pytest -q cookiekit/tests
```

Lock check:

```bash
uv lock --check
```

Build publishable artifacts:

```bash
uv build --package cookiekit --no-sources
```

## Release and CI

- Release workflow: [`cookiekit/docs/release.md`](cookiekit/docs/release.md)
- Changelog: [`cookiekit/CHANGELOG.md`](cookiekit/CHANGELOG.md)
- CI workflow: [`.github/workflows/cookiekit-ci.yml`](.github/workflows/cookiekit-ci.yml)

## Current Status

Phase status in [`todo.md`](todo.md):
- Phases 1-5 are complete.
- Next planned item: define post-`0.1.0` scope.
