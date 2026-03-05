"""CLI for downloadkit."""

from __future__ import annotations

import argparse
import json
import re
import sys

from requestkit import SessionConfig

from .diagnostics import summarize_result
from .download import DownloadConfig, fetch

_RATE_RE = re.compile(r"^\s*(\d+)\s*([kmg]?i?b?)?\s*$", re.IGNORECASE)


def _parse_rate(value: str) -> int:
    match = _RATE_RE.fullmatch(value)
    if not match:
        raise argparse.ArgumentTypeError(f"Invalid rate value: {value!r}")

    amount = int(match.group(1))
    suffix = (match.group(2) or "").lower()
    factors = {
        "": 1,
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "kib": 1024,
        "m": 1024 * 1024,
        "mb": 1024 * 1024,
        "mib": 1024 * 1024,
        "g": 1024 * 1024 * 1024,
        "gb": 1024 * 1024 * 1024,
        "gib": 1024 * 1024 * 1024,
    }
    return amount * factors[suffix]


def _parse_header(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("Expected HEADER:VALUE")
    name, header_value = value.split(":", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("Header name cannot be empty")
    return name, header_value.strip()


def _cmd_fetch(args: argparse.Namespace) -> int:
    headers = dict(args.header or ())
    config = DownloadConfig(
        output=args.output,
        overwrite=args.overwrite,
        resume=args.resume,
        rate_limit=args.rate,
        headers=headers,
        fallback_urls=tuple(args.fallback or ()),
        request=SessionConfig(
            browser=args.browser,
            user_agent=args.user_agent,
            referer=args.referer,
            proxy=args.proxy,
            timeout=args.timeout,
            retries=args.retry,
            cookies=args.cookies,
        ),
    )

    try:
        result = fetch(args.url, config)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "failed", "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"Download error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summarize_result(result), indent=2, sort_keys=True))
        return 0

    print(f"{result.status}: {result.output} <- {result.used_url}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="downloadkit",
        description="Download toolkit for practical file transfer workflows.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="downloadkit 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Download a URL to a file.",
    )
    fetch_parser.add_argument("url", help="Source URL")
    fetch_parser.add_argument("-o", "--output", required=True, help="Output file path")
    fetch_parser.add_argument("--cookies", help="Path to Netscape cookies.txt")
    fetch_parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    fetch_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output")
    fetch_parser.add_argument("--retry", type=int, default=4, help="Retry count")
    fetch_parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    fetch_parser.add_argument("--rate", type=_parse_rate, help="Optional byte rate limit, e.g. 500k or 2m")
    fetch_parser.add_argument("--header", action="append", type=_parse_header, help="Extra request header")
    fetch_parser.add_argument("--fallback", action="append", help="Fallback URL to try if the primary fails")
    fetch_parser.add_argument("--json", action="store_true", help="Print machine-readable result JSON")
    fetch_parser.add_argument("--browser", choices=("chrome", "firefox"), help="Browser-like header preset")
    fetch_parser.add_argument("--user-agent", help="Override the User-Agent header")
    fetch_parser.add_argument("--referer", help="Set the Referer header")
    fetch_parser.add_argument("--proxy", help="Use a single proxy for HTTP and HTTPS")
    fetch_parser.set_defaults(func=_cmd_fetch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
