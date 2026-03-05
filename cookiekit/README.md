# cookiekit

Cookie extraction, validation, and sync toolkit for downloader workflows.

`cookiekit` ships as:
- A Python library for loading, selecting, validating, and extracting cookies.
- A CLI (`cookiekit`) for cookie-only workflows, including browser-source sync.

## Install

From source workspace:

```bash
uv sync --package cookiekit
```

From built artifact:

```bash
uv build --package cookiekit --no-sources
python -m pip install dist/cookiekit-*.whl
```

## CLI

Show help:

```bash
uv run --package cookiekit cookiekit --help
```

Core commands:

```bash
uv run --package cookiekit cookiekit load path/to/cookies.txt
uv run --package cookiekit cookiekit save --input in.txt --output out.txt
uv run --package cookiekit cookiekit check path/to/cookies.txt --require sessionid
uv run --package cookiekit cookiekit parse-spec "firefox/.example.com::Work"
uv run --package cookiekit cookiekit sync --source a.txt --source b.txt --select rotate
uv run --package cookiekit cookiekit noop --source cookies.txt --cookies-update auto
```

### Source Selection

Use multiple `--source` values and one selection mode:
- `first` (default)
- `random` (`--random-seed` for deterministic behavior)
- `rotate` (persistent index via `--rotate-state-file`)

Example:

```bash
uv run --package cookiekit cookiekit sync \
  --source cookies-primary.txt \
  --source browser:firefox/.example.com:default-release \
  --select rotate \
  --rotate-state-file .cookiekit.rotate-state.json \
  --cookies-update auto
```

### Browser Source Spec

Browser sources use:

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

### Update Behavior

`--cookies-update` controls persistence after loading selected source:
- `auto`: update selected file source only (browser source does not auto-write)
- `off`: do not persist
- `<path>`: always write to explicit path

## Stable Library API (V1)

Public imports are re-exported from `cookiekit`:

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

### Minimal Library Example

```python
from cookiekit import parse_source, load_source, check_required_cookies

source = parse_source("browser:firefox/.example.com:default-release")
loaded = load_source(source)
result = check_required_cookies(loaded.cookies, ["sessionid"], domain=".example.com")
print(result.ok, result.missing, result.expired)
```

## Browser Decryption Notes

- Chromium encrypted-cookie decryption uses `pycryptodome`.
- Linux keyring extraction uses `secretstorage` for GNOME keyring and `kwallet-query` for KWallet.
- If AES/keyring access is unavailable, decryption failures are counted and surfaced by diagnostics instead of crashing.

## Development

Run tests:

```bash
uv run --package cookiekit --group dev pytest -q
```

Build:

```bash
uv build --package cookiekit --no-sources
```
