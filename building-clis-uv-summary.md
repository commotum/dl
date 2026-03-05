# Building CLIs With uv: Summary

This document extracts the `uv`-specific CLI and tooling guidance from [`V1/cookie-uv.md`](V1/cookie-uv.md).

It intentionally omits the cookie-specific implementation phases and keeps only the parts that are useful when packaging, running, building, and shipping Python CLIs with `uv`.

## Recommended Default

For a Python project that should be both importable and runnable as a CLI:

- use `uv init --package <name>`
- keep the code in one packaged project until there is a clear reason to split it
- define the CLI entrypoint in `[project.scripts]`

Why:

- you get an installable package and a CLI in one place
- `uv run`, `uvx`, and `uv tool install` all work cleanly
- build and publish flows stay straightforward

## Minimal Project Pattern

Useful `pyproject.toml` pieces:

```toml
[project]
name = "mycli"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
mycli = "mycli.cli:main"

[dependency-groups]
dev = ["pytest", "ruff", "mypy"]
```

## Dependency Model

Use the right section for the right dependency type:

- `[project.dependencies]`: runtime dependencies that ship to users
- `[project.optional-dependencies]`: published extras
- `[dependency-groups]`: local dev/test tooling
- `[tool.uv.sources]`: local path/git/index overrides during development

Important rule:

- run `uv build --no-sources` before release to validate that your package metadata does not rely on local-only source overrides

## Day-To-Day Workflow

Common commands:

```bash
uv sync
uv run mycli --help
uv run pytest
uv lock
uv lock --check
```

Useful reproducibility flags:

- `uv run --locked ...`
- `uv run --frozen ...`
- `uv sync --frozen`

Key behavior:

- `uv run` automatically locks and syncs by default
- `uv sync` is exact by default

## Build And Release Gate

Reasonable release gate:

```bash
uv run pytest
uv lock --check
uv build --no-sources --sdist --wheel
```

Publishing:

```bash
uv publish
```

Useful publish options from the original review:

- `--index`
- `--check-url`
- `--token`
- `--no-attestations`

## Delivery Modes

`uv` supports three useful ways to deliver a CLI:

- local project development: `uv run mycli ...`
- ephemeral tool use: `uvx --from mycli mycli ...`
- persistent user install: `uv tool install mycli`

That makes it reasonable to ship a single packaged project that works for:

- library imports
- repo-local development
- one-off agent execution
- installed end-user CLI usage

## Scripts And Tools

Useful supporting patterns:

- `uv run --script script.py` for standalone scripts
- PEP 723 inline metadata for script dependencies
- `uv tool run` / `uvx` for disposable CLI execution

These are useful when you do not want a full project install, but they are secondary to a packaged CLI if the tool is meant to be reused.

## Workspace Note

Use a workspace only if it provides real value.

Good reasons:

- separate core library and thin CLI wrapper
- shared lockfile across closely related packages

Reasons not to split yet:

- unnecessary complexity for a compact tool
- no clear release or testing benefit

Default recommendation:

- start with one packaged project
- split into a workspace later only if the codebase or release model clearly demands it

## Debugging And Inspection

Helpful commands:

```bash
uv help <command>
uv self version
uv -v ...
uv -vv ...
```

These are useful when debugging CLI packaging, lockfile behavior, or environment drift.

## Practical Takeaway

For most Python CLIs, the simplest good path is:

1. `uv init --package <name>`
2. add a `[project.scripts]` entrypoint
3. keep runtime deps minimal
4. keep dev tools in `[dependency-groups]`
5. use `uv run` during development
6. ship with `uv build --no-sources`
7. support `uvx` and `uv tool install` as the main end-user execution modes
