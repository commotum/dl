# CookieKit Roadmap TODO

## Phase 1: Core model + cookie file I/O

Status: complete

- [x] Browser spec parser (no browser DB extraction yet)
- [x] `cookies.txt` read/write compatibility
- [x] Atomic write path (`.tmp` then replace)
- [x] Library API + CLI commands: `load`, `save`, `check`
- [x] Tests for parser edge cases and round-trip write
- [x] CLI import/export diagnostics

Notes:
- Implemented in `cookiekit/src/cookiekit/{spec.py,cookiestxt.py,persist.py,checks.py,cli.py}`
- Tests in `cookiekit/tests/` currently pass

## Phase 2: Source selection + session behavior

Status: complete (file-source scope)

- [x] Multi-source handling (`list` of sources)
- [x] `random` and `rotate` selectors
- [x] `cookies-update` behavior equivalents
- [x] `noop`-style cookie-only command flow
- [x] Deterministic rotation tests
- [x] Safe persistence tests for repeated invocations

Implementation target:
- Added `sources.py` and `selectors.py`
- Extended CLI with source selection + update target options (`sync`/`noop`)
- Browser-source extraction remains intentionally deferred to Phase 3

## Phase 3: Browser extraction (Firefox + Chromium + WebKit)

Status: complete (Phase 4 decryption deferred)

- [x] Profile discovery
- [x] Domain filtering
- [x] Firefox container filtering
- [x] SQLite lock-safe read strategy (ro/immutable then copy fallback)
- [x] Cross-platform SQL behavior fixtures/tests
- [x] Clear unsupported browser/keyring errors

Notes:
- Implemented in `cookiekit/src/cookiekit/browser.py`
- Browser sources now wired through `cookiekit/src/cookiekit/sources.py`
- Added tests in `cookiekit/tests/test_browser.py`
- Chromium encrypted-cookie decryption is intentionally deferred to Phase 4

## Phase 4: Decryption hardening + diagnostics

Status: pending

- [ ] OS-specific decrypt paths (Linux/macOS/Windows)
- [ ] Per-mode decryption failure accounting
- [ ] Redacted logging for sensitive values
- [ ] Decrypt failure-mode tests
- [ ] Log redaction tests

## Phase 5: Packaging + external consumption

Status: partially started

- [x] Package scaffold + CLI entrypoint
- [ ] Stable library API docs
- [ ] Expanded CLI docs/examples
- [ ] Versioning + changelog workflow
- [ ] Build/publish workflow docs/commands
- [ ] `uv build --no-sources` clean run gate
- [ ] Install/import smoke test from built artifact

## Immediate next tasks

- [ ] Start Phase 4 decryption implementation (Linux/macOS/Windows)
- [ ] Add decrypt failure accounting and diagnostics
- [ ] Add log redaction behavior and tests
