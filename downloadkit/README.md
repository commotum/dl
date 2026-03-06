# downloadkit

`downloadkit` is the file-transfer layer for this workspace.

It is meant for "take this URL and land the file correctly on disk."

## Current scope

- atomic file writes
- resume support
- fallback URLs
- response validation
- robust single-file fetches

Recommended CLI path from the workspace root:

```bash
uv run dl downloadkit --help
```

Direct package invocation also works:

```bash
uv run --package downloadkit downloadkit --help
```

## CLI

Current command:

- `downloadkit fetch URL -o PATH`

Supported flags:

- `--cookies`
- `--resume` / `--no-resume`
- `--overwrite`
- `--retry`
- `--timeout`
- `--rate`
- `--header`
- `--fallback`
- `--json`
- `--browser`
- `--user-agent`
- `--referer`
- `--proxy`

Examples:

```bash
uv run dl downloadkit fetch https://example.com/file.bin -o file.bin
```

```bash
uv run dl downloadkit fetch \
  https://example.com/file.bin \
  -o file.bin \
  --cookies cookies.txt \
  --fallback https://mirror.example.com/file.bin \
  --json
```

Behavior:

- if the output file already exists and `--overwrite` is not set, the download is skipped
- if a `.part` file exists and resume is enabled, `downloadkit` sends `Range` and attempts to resume
- if the server returns HTML for a non-HTML target, the download fails instead of saving a login or challenge page as a binary file
- if the primary URL fails validation or transfer, fallback URLs are tried in order

## Library

```python
from downloadkit import DownloadConfig, fetch
from requestkit import SessionConfig

result = fetch(
    "https://example.com/file.bin",
    DownloadConfig(
        output="file.bin",
        fallback_urls=("https://mirror.example.com/file.bin",),
        request=SessionConfig(cookies="cookies.txt", browser="chrome"),
    ),
)

print(result.status)
print(result.output)
```

Useful public imports:

```python
from downloadkit import (
    DownloadConfig,
    DownloadError,
    DownloadResult,
    DownloadValidationError,
    detect_file_signature,
    fetch,
    summarize_result,
)
```

## Notes

- `downloadkit` uses `requestkit` for session/request behavior.
- `downloadkit` accepts Netscape `cookies.txt`; browser extraction itself stays in `cookiekit`.
- The root `dl` wrapper is only a dispatcher. The actual CLI surface still lives in `downloadkit`.
