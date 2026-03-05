# cookiekit

V1 standalone cookie library + CLI.

## CLI

```bash
uv run cookiekit --help
uv run cookiekit load path/to/cookies.txt
uv run cookiekit save --input in.txt --output out.txt
uv run cookiekit check path/to/cookies.txt --require sessionid
uv run cookiekit parse-spec "firefox/.example.com::Work"
```
