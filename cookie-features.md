# gallery-dl Cookie System: Feature Inventory

This document captures what `gallery-dl` does around cookies, browser extraction, session persistence, and auth workflows, with emphasis on what is useful for a downloader/automation agent.

## 1) Cookie Input UX: many ways in, one runtime model

1. Supports three cookie source types through one config key (`extractor.*.cookies`):
   - Netscape/Mozilla `cookies.txt` file path.
   - Name/value object (cookie dict).
   - Browser extraction spec list.
2. Browser extraction spec supports up to 5 parts:
   - browser name.
   - optional profile name or absolute profile path.
   - optional keyring override.
   - optional Firefox container.
   - optional domain filter (prefix `.` includes subdomains).
3. Command-line cookie UX is simple and complete:
   - `-C/--cookies FILE`
   - `--cookies-export FILE`
   - `--cookies-from-browser BROWSER[/DOMAIN][+KEYRING][:PROFILE][::CONTAINER]`
4. README docs present the same three intake methods users expect:
   - exported cookies file, devtools copy/paste values, browser extraction.

Why this is smart for agents:
- You can plug in whichever credential source is available at runtime without changing extraction code.
- Same internal cookiejar regardless of origin means less branching in your agent.

## 2) Smart source selection and rotation

1. `cookies-select` can treat `cookies` as a list of sources.
2. Supports `random` selection for distribution across identities/sessions.
3. Supports `rotate` selection for deterministic round-robin behavior.
4. Uses a class-level index to keep rotation state across extractor runs.

Why this is smart for agents:
- Easy session sharding across multiple accounts/cookie jars.
- Built-in anti-burst pattern without custom scheduler logic.

## 3) Session persistence and export lifecycle

1. `cookies-update` defaults to `true`.
2. Two persistence modes:
   - `cookies-update: "/path/file.txt"`: always write there.
   - `cookies-update: true` + source is cookies file path: update that file.
3. Cookie writes are atomic:
   - write to `path.tmp`, then `os.replace()` to final path.
4. Persistence is triggered at finalize (`job.handle_finalize()`), not ad hoc.
5. `noop` extractor explicitly saves cookies too, enabling cookie-only runs.
6. If no URL is given but cookie input exists (`--cookies-from-browser` or config cookies), CLI auto-runs `noop`.

Why this is smart for agents:
- You can run "refresh cookie jar" as a standalone operation.
- Atomic write avoids partially-written cookie files during crashes.
- Default persistence reduces accidental stale-session drift.

## 4) Browser extraction engine: depth and resilience

1. Supports multiple browser families:
   - Chromium: `brave`, `chrome`, `chromium`, `edge`, `opera`, `thorium`, `vivaldi`
   - Firefox family: `firefox`, `librewolf`, `zen`, `floorp`
   - WebKit: `safari`, `orion`
2. Cross-platform browser profile discovery:
   - Windows, macOS, Linux paths.
   - Firefox Linux paths include modern, legacy, Flatpak, and Snap locations.
3. Profile resolution strategy:
   - If exact profile path contains target DB file, prefer immediately.
   - Else search recursively and choose most recently used DB.
4. Domain filtering is supported for browser extraction:
   - exact host filter.
   - subdomain-inclusive filter via leading dot (`.example.com`).
5. Firefox container support:
   - `none` (default), `all`, or specific named container.
   - Reads `containers.json` and maps container name/l10n ID to `userContextId`.
6. Browser spec is validated early:
   - unsupported browser/keyring raises clear errors.

Why this is smart for agents:
- Works across diverse host environments without per-machine custom scripts.
- Domain/container filters minimize cookie scope, reducing noise and auth ambiguity.

## 5) SQLite handling: avoids lock pain and handles real-world setups

1. Tries SQLite read-only immutable URI first (`mode=ro&immutable=1`) for cookie DBs.
2. Falls back to temporary copied DB if immutable open fails.
3. Escapes `?` and `#` in DB paths before URI open.
4. Uses non-thread-locked sqlite connection mode for robustness in this workflow.

Why this is smart for agents:
- Browser DB locks are common; fallback path keeps jobs running.
- Read-only first avoids unnecessary copies and lock contention.

## 6) Chromium decryption support is production-grade

1. OS-specific decryptors:
   - Linux: v10/v11 AES-CBC (with keyring handling).
   - macOS: keychain-backed AES-CBC for v10; plaintext fallback for old format.
   - Windows: Local State key + AES-GCM (v10), DPAPI fallback for older format.
2. Linux keyring handling:
   - auto-detects backend from desktop environment (`kwallet`, `gnomekeyring`, `basictext`).
   - allows explicit keyring override from browser spec.
3. Tries multiple decryption paths where needed (e.g., Linux empty-key fallback).
4. Tracks/logs decrypt breakdown and failed counts.
5. Handles Chromium timestamp conversion (`expires_utc` to Unix epoch).

Why this is smart for agents:
- Real browser cookies are often encrypted; this is the hard part most tools skip.
- Keyring override is crucial for headless/server environments with unusual backend selection.

## 7) Cookiejar lifecycle in extractor core is flexible

1. `cookies_load()` accepts:
   - dict -> `cookies_update_dict()`
   - file path -> parse Netscape file
   - list/tuple -> browser extraction
2. Browser-extracted cookie sets are memoized in `CACHE_COOKIES` by source tuple.
3. `cookies_update()` accepts dict, iterable of `Cookie`, or single cookie.
4. `cookies_update_dict()` applies domain scoping consistently.

Why this is smart for agents:
- Allows merging cookies from heterogeneous sources at runtime.
- Memoization reduces repeated expensive browser decrypt operations.

## 8) Cookie health/intelligence checks

1. `cookies_check()` validates required cookie names.
2. Domain-aware checks:
   - exact domain by default.
   - optional subdomain matching.
3. Expiration-aware checks:
   - warns for expired cookies.
   - warns when cookies expire in less than 24h.
4. Many extractors define `cookies_names` + `cookies_domain` and call `cookies_check()` before login.
5. If required cookies exist, extractors often skip login entirely.
6. Several extractors emit targeted warnings when key session cookies are missing.

Why this is smart for agents:
- Lets your workflow fail early with actionable auth diagnostics.
- Avoids unnecessary login traffic and CAPTCHA encounters when valid cookies already exist.

## 9) Netscape cookie file parser/writer is robust

1. Loader handles real-world file quirks:
   - strips `#HttpOnly_`.
   - ignores comments (`#`, `$`) and empty lines.
   - tolerates missing-name line form by mapping to value-only cookie representation.
2. Expiry parsing:
   - `0` or empty expiry -> session cookie semantics.
3. Writer outputs standard Netscape header and fields.
4. Writer skips domainless cookies (avoids invalid exported lines).
5. Tests cover parsing/storing edge cases extensively.

Why this is smart for agents:
- Handles messy cookies exported by extensions/tools without hand-fixing files.

## 10) Security and observability features

1. HTTP dump utility can redact auth-bearing headers:
   - masks `Authorization`.
   - masks request `Cookie`.
   - masks response `Set-Cookie`.
2. Cookie load/store errors are warnings, not hard crashes.
3. Cookie subsystem deduplicates repeated warning/error messages to avoid log spam.
4. `--clear-cache MODULE` exists for hygiene/reset of cached sessions/cookies/tokens.

Why this is smart for agents:
- You can troubleshoot HTTP/auth flows with lower secret leakage risk.
- Reduced log spam improves signal for automated monitoring.

## 11) Downloader interoperability

1. `downloader.ytdl.forward-cookies` defaults to `true`.
2. `ytdl` extractor transfers current cookiejar to yt-dlp/youtube-dl instance.
3. The ytdl bridge also parses `cookiesfrombrowser` syntax for downstream modules.

Why this is smart for agents:
- Private/protected media extraction remains authenticated even when delegated.

## 12) Site-specific "smartness" patterns built on cookie primitives

Common patterns across extractors:

1. Prefer existing auth cookies over username/password login.
2. Raise explicit auth-required errors when cookie-only resources are requested.
3. Warn users when expected cookie tokens are absent.
4. Set required non-auth cookies proactively (age gates, feature toggles, etc.).
5. Fall back gracefully when login is impossible or not configured.
6. Cache login results for long intervals (often weeks/months) to reduce repeated auth work.

Examples:
- Exhentai: checks required cookies, falls back to e-hentai when missing auth, and explicitly reports CAPTCHA-driven cookie requirement.
- Furaffinity: warns if expected session cookies (`a`, `b`) are missing.
- Instagram: disables username/password login path and instructs browser cookies; emits hints to refresh stale cookies.
- Subscribestar: checks expected cookie, warns once if absent, and handles adult-domain cookie behavior.

Why this is smart for agents:
- Reduces brittle per-site hacks in your orchestration layer.
- Encodes domain knowledge where it belongs: per extractor.

## 13) Maturity signals from changelog (long-term cookie hardening)

Selected milestones:

1. Implemented `--cookies-from-browser`.
2. Added `--cookies-export` and short `-C`.
3. Added `cookies-select`.
4. Added Firefox container+domain filter support and better defaults.
5. Added support for more browsers (`thorium`, `orion`).
6. Switched cookie save to temp-file atomic strategy.
7. Optimized exact-profile lookup.
8. Improved browser DB read-only strategy to reduce temporary copies.
9. Enabled `cookies-update` by default.

Takeaway:
- Cookie handling is not incidental here; it has been iterated repeatedly over years as a core reliability path.

## 14) What to copy first for a standalone cookie CLI/library

If you want to spin this into an importable standalone package, highest-value reusable pieces are:

1. `gallery_dl/cookies.py` (browser DB discovery + extraction + decryption)
2. `gallery_dl/util.py` cookie file parser/writer (`cookiestxt_load/store`)
3. `extractor/common.py` lifecycle helpers:
   - source loading
   - source selection
   - cookie health checks
   - atomic export/update behavior
4. CLI grammar from `option.py` + parser glue in `__init__.py`.

## Source map (quick pointers)

- Cookie docs: `gallery-dl/docs/configuration.rst` (cookies, cookies-select, cookies-update, ytdl forwarding, cache)
- CLI docs: `gallery-dl/docs/options.md`
- Auth quickstart: `gallery-dl/README.rst`
- Cookie extraction core: `gallery-dl/gallery_dl/cookies.py`
- Cookie lifecycle/core logic: `gallery-dl/gallery_dl/extractor/common.py`
- CLI wiring: `gallery-dl/gallery_dl/option.py`, `gallery-dl/gallery_dl/__init__.py`
- Finalize and persistence trigger: `gallery-dl/gallery_dl/job.py`, `gallery-dl/gallery_dl/extractor/noop.py`
- Cookie file read/write + redaction: `gallery-dl/gallery_dl/util.py`
- Tests: `gallery-dl/test/test_cookies.py`, `gallery-dl/test/test_util.py`, `gallery-dl/test/test_ytdl.py`
- Historical hardening: `gallery-dl/CHANGELOG.md`

## Evidence anchors (path:line)

Use these as direct code/doc anchors when implementing the standalone variant.

- Cookie source types / selection / update docs:
  - `gallery-dl/docs/configuration.rst:765-846`
- CLI cookie options docs:
  - `gallery-dl/docs/options.md:159-167`
- CLI cookie option parser:
  - `gallery-dl/gallery_dl/option.py:686-707`
- `--cookies-from-browser` parser wiring:
  - `gallery-dl/gallery_dl/__init__.py:70-80`
- No-URL -> `noop` behavior for cookie operations:
  - `gallery-dl/gallery_dl/__init__.py:273-276`
- Cookie lifecycle (load/select/store/check):
  - `gallery-dl/gallery_dl/extractor/common.py:655-797`
- Rotation state and cookie cache globals:
  - `gallery-dl/gallery_dl/extractor/common.py:44`
  - `gallery-dl/gallery_dl/extractor/common.py:1221`
- Finalize-time cookie persistence:
  - `gallery-dl/gallery_dl/job.py:621`
- `noop` explicit cookie save:
  - `gallery-dl/gallery_dl/extractor/noop.py:20-24`
- Netscape parser/writer:
  - `gallery-dl/gallery_dl/util.py:404-467`
- HTTP auth/cookie redaction:
  - `gallery-dl/gallery_dl/util.py:256-277`
- Browser support sets and entrypoint:
  - `gallery-dl/gallery_dl/cookies.py:27-49`
- Firefox containers and profile/db lookup:
  - `gallery-dl/gallery_dl/cookies.py:216-266`
- Firefox path discovery (incl. Flatpak/Snap):
  - `gallery-dl/gallery_dl/cookies.py:269-305`
- Chromium path/keyring metadata:
  - `gallery-dl/gallery_dl/cookies.py:431-497`
- OS-specific decryptor selection:
  - `gallery-dl/gallery_dl/cookies.py:499-510`
- Linux keyring auto-detect/override:
  - `gallery-dl/gallery_dl/cookies.py:683-696`
  - `gallery-dl/gallery_dl/cookies.py:804-825`
- SQLite immutable-read with fallback copy:
  - `gallery-dl/gallery_dl/cookies.py:935-965`
- Profile auto-pick + browser spec validation:
  - `gallery-dl/gallery_dl/cookies.py:1113-1149`
- Deduplicated cookie warnings/errors:
  - `gallery-dl/gallery_dl/cookies.py:1157-1166`
- ytdl cookie forwarding:
  - `gallery-dl/gallery_dl/extractor/ytdl.py:84-88`
  - `gallery-dl/docs/configuration.rst:8149-8156`
- Defaults:
  - `gallery-dl/docs/gallery-dl.conf:45-47`
  - `gallery-dl/docs/gallery-dl.conf:1293`
- Cache persistence docs:
  - `gallery-dl/docs/configuration.rst:9916-9917`
- Test coverage anchors:
  - `gallery-dl/test/test_cookies.py:125-235`
  - `gallery-dl/test/test_util.py:405-494`
  - `gallery-dl/test/test_ytdl.py:297-309`
- Changelog milestones:
  - `gallery-dl/CHANGELOG.md:3170`
  - `gallery-dl/CHANGELOG.md:2537-2539`
  - `gallery-dl/CHANGELOG.md:1591-1592`
  - `gallery-dl/CHANGELOG.md:1649`
  - `gallery-dl/CHANGELOG.md:1870-1872`
  - `gallery-dl/CHANGELOG.md:2294`
  - `gallery-dl/CHANGELOG.md:1753`
  - `gallery-dl/CHANGELOG.md:443`
  - `gallery-dl/CHANGELOG.md:4438`
  - `gallery-dl/CHANGELOG.md:4402`
