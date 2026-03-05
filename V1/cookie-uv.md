# Cookie CLI + Library Build Plan (uv-first)

## Scope

This plan is based on:

- `/home/jake/Developer/dl/cookie-features.md` (gallery-dl cookie capability inventory)
- A full review of all files in `/home/jake/Developer/dl/uv-docs` (21 files, including `Commands _ uv.md`)

The goal is to build a standalone cookie package that is:

- Importable as a Python library
- Usable as a CLI
- Easy to install/run with `uv` in projects, scripts, and tool mode

---

## 1) What uv-docs gives us (comprehensive findings)

### Project/package model

- `uv init` supports app and library templates; `--package` and `--lib` create packaged projects with a build system.
- CLI entrypoints are standardized via `[project.scripts]`.
- Packaged projects are installed into `.venv`; non-packaged app templates are not.
- `tool.uv.package` can force package behavior on/off.

### Dependency model

- Core published deps: `[project.dependencies]`
- Published extras: `[project.optional-dependencies]`
- Local/dev deps: `[dependency-groups]` (PEP 735)
- Local source overrides: `[tool.uv.sources]` (index/git/url/path/workspace)
- `--no-sources` is critical for “publishable metadata only” validation.

### Lock/sync behavior

- Automatic lock+sync is default for `uv run`.
- Repro flags:
  - `--locked`: fail if lockfile is outdated
  - `--frozen`: use lockfile without freshness check
  - `--no-sync`: skip env sync
- `uv sync` is exact by default; `--inexact` keeps extras.
- Partial install flags exist for Docker/CI layering (`--no-install-project`, etc.).

### Workspace model

- Workspaces share one `uv.lock`; `uv run/sync --package` targets members.
- Great for core+CLI split in one repo.
- Not ideal when members need conflicting requirements or separate env isolation.

### Scripts/tools model

- `uv run --script` supports PEP 723 inline metadata and script lockfiles (`script.py.lock`).
- `uvx` / `uv tool run` is ideal for ephemeral CLI usage.
- `uv tool install` is ideal for persistent user-level CLI installation.

### Build/publish model

- `uv build` supports `--sdist`, `--wheel`, `--build-constraint`, `--require-hashes`.
- For release confidence, docs explicitly recommend `uv build --no-sources`.
- `uv publish` supports token auth, `--check-url`, named index, and attestations controls (`--no-attestations`).

### Export and compliance model

- `uv export` supports:
  - `requirements.txt`
  - `pylock.toml` (PEP 751)
  - `cyclonedx1.5` (SBOM)

### Debug/help

- `uv help <command>`, `-v/-vv` verbose diagnostics
- `uv self version` for environment/debug reproducibility

---

## 2) Coverage map of all `uv-docs` files

- `uv.md`: top-level capability map (`projects`, `scripts`, `tools`, `pip`, Python management).
- `Getting started _ uv.md`: navigation hub.
- `First steps _ uv.md`: install sanity checks.
- `Features _ uv.md`: command families and intended usage.
- `Getting help _ uv.md`: diagnostics workflow (`help`, verbosity, versioning).
- `Projects_Projects _ uv.md`: projects concept index.
- `Projects_Structure and files _ uv.md`: `pyproject.toml`, `.venv`, `uv.lock`, `pylock.toml` relationship.
- `Projects_Creating projects _ uv.md`: project templates and `--build-backend`.
- `Projects_Managing dependencies _ uv.md`: dependencies/sources/groups/extras/virtual/editable model.
- `Projects_Running commands _ uv.md`: `uv run`, `--with`, script isolation behavior.
- `Projects_Locking and syncing _ uv.md`: automatic lock/sync semantics and reproducibility flags.
- `Projects_Configuring projects _ uv.md`: entry points, build systems, build isolation controls, conflicts.
- `Projects_Building distributions _ uv.md`: `uv build` behavior and reproducible build flags.
- `Projects_Using workspaces _ uv.md`: workspace behavior and tradeoffs.
- `Projects_Exporting a lockfile _ uv.md`: export formats and SBOM notes.
- `Working on projects _ uv.md`: practical end-to-end project workflow.
- `Running scripts _ uv.md`: PEP 723 scripts, lockfiles, and `exclude-newer`.
- `Tools _ uv.md`: tool environment lifecycle and `uvx` vs installed tools.
- `Using tools _ uv.md`: practical tool execution/install patterns.
- `Building and publishing a package _ uv.md`: release workflow, trusted publishing, upload caveats.
- `Commands _ uv.md`: full option surface; validated target flags for init/add/run/sync/lock/export/build/publish/tool/auth.

---

## 3) Recommended architecture for this cookie project

### Recommendation now (v1): single packaged project

Use one package that contains both:

- Library API (`import cookiekit`)
- CLI entrypoint (`cookiekit` command via `[project.scripts]`)

Why:

- Fastest path to usable CLI + importable API.
- Minimal moving pieces while porting sensitive auth/cookie logic.
- Still fully publishable and tool-installable.

### Recommendation later (v2+): split into workspace only if needed

If the codebase grows, split into:

- `cookiekit-core` (library)
- `cookiekit-cli` (thin CLI wrapper)

Use a uv workspace only when the split gives clear test/release value.

---

## 4) Proposed package layout

```text
cookiekit/
  pyproject.toml
  README.md
  src/
    cookiekit/
      __init__.py
      cli.py
      spec.py
      sources.py
      selectors.py
      persist.py
      checks.py
      cookiestxt.py
      browser/
        __init__.py
        chromium.py
        firefox.py
        webkit.py
        profiles.py
        decrypt_linux.py
        decrypt_macos.py
        decrypt_windows.py
  tests/
    test_cookiestxt.py
    test_selectors.py
    test_checks.py
    test_browser_specs.py
```

Feature mapping to `cookie-features.md`:

- Input normalization: `sources.py`, `spec.py`
- Source rotation/random: `selectors.py`
- Atomic save/update: `persist.py`
- Cookie health checks: `checks.py`
- Netscape parser/writer: `cookiestxt.py`
- Browser extraction/decryption: `browser/*`
- CLI ergonomics: `cli.py`

---

## 5) Baseline `uv` setup plan (commands)

### Bootstrap project

```bash
uv init --package cookiekit
cd cookiekit
```

### Add CLI entrypoint + package metadata

- Add `[project.scripts]` with `cookiekit = "cookiekit.cli:main"`.
- Keep `requires-python` explicit.

### Dependency strategy

Use stdlib-first where possible and keep runtime deps minimal.

- Published runtime deps in `[project.dependencies]` only when truly required.
- Published optional features in `[project.optional-dependencies]`:
  - example: `linux-keyring = ["secretstorage; sys_platform == 'linux'"]`
- Local development tooling in `[dependency-groups]`:
  - `dev = ["pytest", "pytest-cov", "ruff", "mypy"]`

Commands:

```bash
uv add --dev pytest pytest-cov ruff mypy
```

### Day-to-day workflow

```bash
uv run cookiekit --help
uv run pytest
uv run ruff check .
uv lock
uv sync
```

### Reproducible CI mode

```bash
uv lock --check
uv sync --frozen
uv run --frozen pytest
```

---

## 6) Implementation phases (cookie-specific)

## Phase 1: Core model + cookie file I/O

Ship first:

- Browser spec parser (without browser DB extraction yet)
- `cookies.txt` read/write compatibility
- Atomic write path (`.tmp` then replace)
- Library API + basic CLI commands:
  - `load`
  - `save`
  - `check`

Acceptance:

- Tests for parser edge-cases and round-trip write.
- CLI can import/export cookies file and print diagnostics.

## Phase 2: Source selection + session behavior

Add:

- Multi-source handling (`list` of sources)
- `random` and `rotate` selectors
- `cookies-update` behavior equivalents
- `noop`-style cookie-only command flow

Acceptance:

- Deterministic rotation tests.
- Safe persistence under repeated CLI invocations.

## Phase 3: Browser extraction (Firefox + Chromium + WebKit)

Add:

- Profile discovery
- Domain filtering
- Firefox container filtering
- SQLite lock-safe read strategy (ro/immutable then copy fallback)

Acceptance:

- Cross-platform test fixtures for SQL query behavior.
- Clear errors for unsupported browser/keyring spec.

## Phase 4: Decryption hardening + diagnostics

Add:

- OS-specific decrypt paths
- Per-mode failure accounting
- Redacted logging for sensitive headers/cookies

Acceptance:

- Decrypt path unit tests and failure-mode tests.
- Log redaction test coverage.

## Phase 5: Packaging + external consumption

Add:

- Stable library API docs
- CLI docs/examples
- Versioning + changelog
- Build/publish workflow

Acceptance:

- Clean `uv build --no-sources` result.
- Install/import smoke test from built artifact.

---

## 7) Publishing and install strategy

### Build gate

```bash
uv run pytest
uv lock --check
uv build --no-sources --sdist --wheel
```

### Publish

```bash
uv publish --index testpypi --check-url https://test.pypi.org/simple
```

Or with token:

```bash
uv publish --token "$UV_PUBLISH_TOKEN"
```

### Post-publish smoke

```bash
uv run --with cookiekit --no-project -- python -c "import cookiekit; print(cookiekit.__version__)"
```

### Optional export artifacts

```bash
uv export --format requirements.txt --output-file requirements.txt
uv export --format pylock.toml --output-file pylock.toml
uv export --format cyclonedx1.5 --output-file sbom.json
```

---

## 8) CLI delivery modes supported by uv

- Project-local execution during development:
  - `uv run cookiekit ...`
- Ephemeral tool-style execution:
  - `uvx --from cookiekit cookiekit ...`
- Persistent user install:
  - `uv tool install cookiekit`

For local path usage in other repos:

```bash
uv add ../cookiekit
```

This will record a path source in `tool.uv.sources` (dev-friendly), and you can validate publishability with `--no-sources`.

---

## 9) Risk log and controls

- License risk (critical): `gallery-dl` is GPL-2.0.
  - If copying code, your package must be license-compatible.
  - If a permissive license is required, implement a clean-room reimplementation.
- Cross-platform auth edge cases:
  - Add fixture-driven tests and explicit unsupported-mode errors.
- Secret leakage risk:
  - Default to redacted logs and avoid printing raw cookie values.
- Reproducibility drift:
  - Enforce `uv lock --check` in CI.
  - Prefer `uv build --no-sources` before every publish.

---

## 10) Immediate next commands (pragmatic start)

```bash
# in /home/jake/Developer/dl
uv init --package cookiekit
cd cookiekit
uv add --dev pytest pytest-cov ruff mypy
uv run python -c "print('cookiekit scaffold ready')"
```

Then implement Phase 1 (`cookiestxt`, `spec`, `cli`) before browser extraction.
