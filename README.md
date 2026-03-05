# cookiekit Workspace

`cookiekit` is a small library and CLI for one primary job:

- read cookies from a browser profile where you are already logged in
- optionally scope them to a target site
- write a Netscape `cookies.txt` file that other tools can use

If you only need one thing from this repo, use `cookiekit export-browser`.

## Fastest path

1. Log in to the target site in your browser.
2. Export cookies from that browser/profile/container.
3. Use the generated `cookies.txt` with your downstream tool.

Workspace install:

```bash
uv sync --package cookiekit
```

Show CLI help:

```bash
uv run --package cookiekit cookiekit --help
```

Export cookies from Chrome for a site:

```bash
uv run --package cookiekit cookiekit export-browser \
  --browser chrome \
  --domain .github.com \
  --output github-cookies.txt
```

Export cookies from Firefox using a specific profile and container:

```bash
uv run --package cookiekit cookiekit export-browser \
  --browser firefox \
  --profile default-release \
  --container Work \
  --domain .instagram.com \
  --output instagram-cookies.txt
```

If you prefer the compact browser-spec form:

```bash
uv run --package cookiekit cookiekit export-browser \
  --spec "chrome/.github.com:Default" \
  --output github-cookies.txt
```

For machine-readable output:

```bash
uv run --package cookiekit cookiekit export-browser \
  --browser chrome \
  --domain .github.com \
  --output github-cookies.txt \
  --json
```

## How To Pick The Right Account

`cookiekit` does not log in for you. It only reads the session that already exists in the browser storage you point it at.

- If the account is in your normal Chrome profile, use `--browser chrome` and optionally `--profile Default`.
- If you keep different accounts in different browser profiles, choose the right `--profile`.
- If you keep different accounts in Firefox containers, use `--container`.
- If you omit `--profile`, `cookiekit` auto-picks the most recently used matching profile database.

Use `--domain` whenever you know the target site.

- `example.com` matches that host.
- `.example.com` matches the host and its subdomains.

This keeps the exported file smaller and reduces noise from unrelated cookies.

## Browser Support

Supported browsers:

- Chromium family: `brave`, `chrome`, `chromium`, `edge`, `opera`, `thorium`, `vivaldi`
- Firefox family: `firefox`, `librewolf`, `zen`, `floorp`
- WebKit family: `safari`, `orion`

Supported extraction features:

- Cross-platform profile discovery on Linux, macOS, and Windows
- Firefox container filtering
- SQLite read-only immutable mode with copy fallback
- Chromium encrypted-cookie decryption
- Netscape `cookies.txt` export

Linux Chromium notes:

- `--keyring kwallet`
- `--keyring gnomekeyring`
- `--keyring basictext`

Only Chromium-family browsers accept `--keyring`.

## CLI Guide

### Primary command: `export-browser`

This is the command most users and agents want.

Inputs:

- `--browser <name>` plus optional `--profile`, `--domain`, `--container`, `--keyring`
- or `--spec "<BROWSER[/DOMAIN][+KEYRING][:PROFILE][::CONTAINER]>"` if you already have a full spec string

Output:

- `-o/--output/--cookies-export <path>` writes Netscape `cookies.txt`

Other useful flags:

- `--json` prints a structured summary
- `--no-atomic` writes directly instead of temp-file replace

Examples:

```bash
# Auto-pick the most recently used Chrome profile
uv run --package cookiekit cookiekit export-browser \
  --browser chrome \
  --domain .x.com \
  --output twitter-cookies.txt

# Explicit Firefox profile path
uv run --package cookiekit cookiekit export-browser \
  --browser firefox \
  --profile ~/.mozilla/firefox/abcd1234.default-release \
  --domain .reddit.com \
  --output reddit-cookies.txt

# Safari / Orion on macOS
uv run --package cookiekit cookiekit export-browser \
  --browser safari \
  --domain .patreon.com \
  --output patreon-cookies.txt
```

### Other commands

These are useful, but they are secondary to `export-browser`:

- `parse-spec`: parse a browser spec and print JSON
- `load`: load a `cookies.txt` file and print a summary
- `save`: copy/normalize a `cookies.txt` file
- `check`: verify required cookies by name/domain/expiration
- `sync` / `noop`: advanced multi-source flows with file sources, browser sources, `first`/`random`/`rotate`, and `cookies-update`

Advanced example:

```bash
uv run --package cookiekit cookiekit sync \
  --source cookies-primary.txt \
  --source browser:firefox/.example.com:default-release::Work \
  --source browser:chrome/.example.com+kwallet:Default \
  --select rotate \
  --rotate-state-file .cookiekit.rotate-state.json \
  --cookies-update auto
```

## Library Usage

Fastest library path:

```python
from cookiekit import export_browser_cookies

result = export_browser_cookies(
    "chrome/.github.com:Default",
    "github-cookies.txt",
)
print(result.cookie_count)
print(result.output)
```

If you want cookies in memory without writing a file:

```python
from cookiekit import load_browser_cookies, parse_browser_spec

spec = parse_browser_spec("firefox/.instagram.com:default-release::Work")
cookies = load_browser_cookies(spec)
print(len(cookies))
```

Stable public imports:

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

## Troubleshooting

- If Chrome/Chromium export returns fewer cookies than expected on Linux, try an explicit `--keyring`.
- If you use multiple Firefox containers, make sure you pass the right `--container`.
- If you are unsure which browser profile holds the login, start without `--profile`, then tighten it once you identify the right one.
- If the target tool needs Netscape cookies, use `export-browser`; that is the default output format.

## Repo Layout

- `cookiekit/`: Python package
- `cookiekit/src/cookiekit/`: implementation modules
- `cookiekit/tests/`: test suite
- `cookiekit/docs/release.md`: build/release workflow
- `V1/`: original planning docs and feature inventory
- `building-clis-uv-summary.md`: extracted `uv` summary for packaging CLIs and tools
- `gallery-dl/`: retained reference codebase/submodule

## Related Docs

- Package README: [`cookiekit/README.md`](cookiekit/README.md)
- `uv` tooling summary: [`building-clis-uv-summary.md`](building-clis-uv-summary.md)
- V1 feature inventory: [`V1/cookie-features.md`](V1/cookie-features.md)
- V1 roadmap: [`V1/todo.md`](V1/todo.md)
- Release workflow: [`cookiekit/docs/release.md`](cookiekit/docs/release.md)
