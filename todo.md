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

Status: pending

- [ ] Profile discovery
- [ ] Domain filtering
- [ ] Firefox container filtering
- [ ] SQLite lock-safe read strategy (ro/immutable then copy fallback)
- [ ] Cross-platform SQL behavior fixtures/tests
- [ ] Clear unsupported browser/keyring errors

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

- [ ] Start Phase 3 browser extraction implementation
- [ ] Implement Firefox profile/container/domain filtering
- [ ] Implement Chromium profile/domain extraction scaffolding
- [ ] Add SQLite read-only/immutable + copy fallback path
