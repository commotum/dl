# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Phase 1 core cookie model and Netscape `cookies.txt` read/write support.
- Phase 2 multi-source selection (`first`, `random`, `rotate`) and `cookies-update` behavior.
- Phase 3 browser extraction for Firefox, Chromium, and WebKit sources.
- Phase 4 Chromium decryption hardening, per-mode failure accounting, and redacted diagnostics helpers.
- Phase 5 packaging baseline, stable API docs, CLI docs/examples, and build/smoke workflows.

## [0.1.0] - 2026-03-05

### Added
- Initial `cookiekit` release with library + CLI for cookie-only downloader workflows.
