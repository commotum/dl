"""CLI for requestkit."""

from __future__ import annotations

import argparse
import json
import sys

from .diagnostics import format_exchange, is_textual_content_type, summarize_response
from .session import SUPPORTED_BROWSERS, RequestClient, SessionConfig


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("url", help="Request URL")
    parser.add_argument(
        "--browser",
        choices=tuple(sorted(SUPPORTED_BROWSERS)),
        help="Apply a browser-like header preset.",
    )
    parser.add_argument("--user-agent", help="Override the User-Agent header.")
    parser.add_argument("--referer", help="Set the Referer header.")
    parser.add_argument("--proxy", help="Use a single proxy for HTTP and HTTPS.")
    parser.add_argument("--cookies", help="Load cookies from a Netscape cookies.txt file.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=4, help="Number of retry attempts.")
    parser.add_argument(
        "--sleep-request",
        type=float,
        default=0.0,
        help="Minimum delay between requests in seconds.",
    )
    parser.add_argument(
        "--sleep-429",
        type=float,
        default=60.0,
        help="Delay after HTTP 429 in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable output instead of plain text.",
    )


def _build_config(args: argparse.Namespace) -> SessionConfig:
    return SessionConfig(
        browser=args.browser,
        user_agent=args.user_agent,
        referer=args.referer,
        proxy=args.proxy,
        timeout=args.timeout,
        retries=args.retries,
        sleep_request=args.sleep_request,
        sleep_429=args.sleep_429,
        cookies=args.cookies,
    )


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _cmd_get(args: argparse.Namespace) -> int:
    client = RequestClient(_build_config(args))
    response = client.request(args.url)

    if args.json:
        _print_json(summarize_response(response, include_body=True))
        return 0

    content_type = response.headers.get("Content-Type")
    if is_textual_content_type(content_type):
        if response.encoding is None:
            response.encoding = response.apparent_encoding or "utf-8"
        sys.stdout.write(response.text)
        if response.text and not response.text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        sys.stdout.buffer.write(response.content)
    return 0


def _cmd_dump(args: argparse.Namespace) -> int:
    client = RequestClient(_build_config(args))
    response = client.request(args.url)

    if args.json:
        payload = summarize_response(response, include_body=True)
        payload["exchange"] = format_exchange(response)
        _print_json(payload)
        return 0

    sys.stdout.write(format_exchange(response))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="requestkit",
        description="Request/session toolkit for practical downloader workflows.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="requestkit 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get", help="Fetch a URL and print the response body.")
    _add_common_options(get_parser)
    get_parser.set_defaults(func=_cmd_get)

    dump_parser = subparsers.add_parser(
        "dump",
        help="Fetch a URL and print a redacted request/response dump.",
    )
    _add_common_options(dump_parser)
    dump_parser.set_defaults(func=_cmd_dump)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
