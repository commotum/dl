# CookieKit Build and Release Workflow

## 1) Preconditions

- Working tree clean enough for a release.
- `uv` installed.
- Python 3.10+ available.

## 2) Sync and Test

```bash
uv lock
uv run --package cookiekit --group dev pytest -q
```

## 3) Build Publishable Artifacts

Always use `--no-sources` for publishable metadata checks:

```bash
uv build --package cookiekit --no-sources
```

Expected outputs in `dist/`:
- `cookiekit-<version>.tar.gz`
- `cookiekit-<version>-py3-none-any.whl`

## 4) Smoke Test From Built Artifact

Install and import in an isolated virtual environment:

```bash
tmp_dir="$(mktemp -d)"
python -m venv "$tmp_dir/venv"
wheel="$(ls -1 dist/cookiekit-*.whl | head -n1)"
"$tmp_dir/venv/bin/pip" install "$wheel"
"$tmp_dir/venv/bin/python" -c "import cookiekit; print(cookiekit.__version__)"
"$tmp_dir/venv/bin/cookiekit" --help >/dev/null
```

Alternative when shell globbing is preferred:

```bash
"$tmp_dir/venv/bin/pip" install dist/cookiekit-*.whl
```

Alternative using `uv` isolated env:

```bash
wheel="$(ls -1 dist/cookiekit-*.whl | head -n1)"
uv run --no-project --isolated --with "$wheel" python -c "import cookiekit; print(cookiekit.__version__)"
```

If network access is unavailable, run an artifact-only smoke gate:

```bash
"$tmp_dir/venv/bin/pip" install --no-deps "$wheel"
"$tmp_dir/venv/bin/python" -c "import cookiekit; print(cookiekit.__version__)"
```

## 5) Version and Changelog

1. Update version in `cookiekit/pyproject.toml`.
2. Update `cookiekit/src/cookiekit/__init__.py` `__version__`.
3. Move release notes from `## [Unreleased]` into a new `## [x.y.z] - YYYY-MM-DD` section in `cookiekit/CHANGELOG.md`.

## 6) Publish (when ready)

Build artifacts:

```bash
uv build --package cookiekit --no-sources
```

Upload artifacts with your package index workflow (for example, Twine or CI publish job).

## 7) Post-release

- Confirm install path in a clean environment.
- Tag source control with release version (`vX.Y.Z`).
- Start a fresh `## [Unreleased]` section in `CHANGELOG.md`.
