# cookiekit

`cookiekit` is a compact library and CLI for exporting cookies from browsers where you are already logged in.

Primary use case:

- select a browser/profile/container that already has the session you want
- optionally filter to a target domain
- write a Netscape `cookies.txt` file

Recommended CLI path from the workspace root:

```bash
uv run dl cookiekit --help
```

Direct package invocation also works:

```bash
uv run --package cookiekit cookiekit --help
```

## Install

From this workspace:

```bash
uv sync --package cookiekit
```

From a built artifact:

```bash
uv build --package cookiekit --no-sources
python -m pip install dist/cookiekit-*.whl
```

## Fastest CLI Path

Show help:

```bash
uv run dl cookiekit --help
```

Export cookies from Chrome:

```bash
uv run dl cookiekit export-browser \
  --browser chrome \
  --domain .github.com \
  --output github-cookies.txt
```

Export cookies from Firefox using a profile and container:

```bash
uv run dl cookiekit export-browser \
  --browser firefox \
  --profile default-release \
  --container Work \
  --domain .instagram.com \
  --output instagram-cookies.txt
```

Use a full browser spec if you already have one:

```bash
uv run dl cookiekit export-browser \
  --spec "chrome/.github.com:Default" \
  --output github-cookies.txt
```

Machine-readable summary:

```bash
uv run dl cookiekit export-browser \
  --browser chrome \
  --domain .github.com \
  --output github-cookies.txt \
  --json
```

## Browser Arguments

Supported browsers:

- Chromium family: `brave`, `chrome`, `chromium`, `edge`, `opera`, `thorium`, `vivaldi`
- Firefox family: `firefox`, `librewolf`, `zen`, `floorp`
- WebKit family: `safari`, `orion`

Important flags:

- `--profile`: browser profile name or path. Omit it to auto-pick the most recently used matching profile.
- `--domain`: optional site filter. Use `.example.com` to include subdomains.
- `--container`: Firefox-only container selection.
- `--keyring`: Chromium-only Linux keyring override (`kwallet`, `gnomekeyring`, `basictext`).
- `--json`: print a machine-readable summary for agents or scripts.
- `--no-atomic`: write directly to the output path instead of temp-file replace.

## Library

One-shot export:

```python
from cookiekit import export_browser_cookies

result = export_browser_cookies(
    "chrome/.github.com:Default",
    "github-cookies.txt",
)
print(result.cookie_count)
```

In-memory load:

```python
from cookiekit import load_browser_cookies, parse_browser_spec

spec = parse_browser_spec("firefox/.instagram.com:default-release::Work")
cookies = load_browser_cookies(spec)
print(len(cookies))
```

Stable imports:

```python
from cookiekit import (
    BrowserExportResult,
    BrowserSpec,
    CheckResult,
    CookieSource,
    LoadedCookies,
    check_required_cookies,
    dumps_cookies_txt,
    export_browser_cookies,
    load_browser_cookies,
    load_cookies_txt,
    load_rotate_index,
    load_source,
    parse_browser_spec,
    parse_source,
    redact_header_value,
    redact_headers,
    redact_http_header_lines,
    resolve_update_target,
    save_cookies_txt,
    save_rotate_index,
    select_source,
)
```

## Other CLI Commands

- `parse-spec`: parse a browser spec and print JSON
- `load`: load a `cookies.txt` file and print a summary
- `save`: copy/normalize a `cookies.txt` file
- `check`: verify required cookies by name/domain/expiration
- `sync` / `noop`: advanced multi-source flows with file sources, browser sources, and source selection

## Notes

- `cookiekit` does not log in to sites. It only reads existing browser sessions.
- If you maintain multiple accounts, keep them in separate browser profiles or Firefox containers and select the right one at export time.
- Chromium encrypted-cookie decryption uses `pycryptodome`.
- Linux keyring access uses `secretstorage` for GNOME keyring and `kwallet-query` for KWallet.
- The root `dl` wrapper is only a dispatcher. The actual CLI surface still lives in `cookiekit`.
