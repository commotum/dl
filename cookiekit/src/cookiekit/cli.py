"""CLI for cookiekit V1."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .checks import check_required_cookies
from .cookiestxt import load_cookies_txt, save_cookies_txt
from .spec import parse_browser_spec


def _cmd_parse_spec(args: argparse.Namespace) -> int:
    spec = parse_browser_spec(args.spec)
    print(json.dumps(asdict(spec), indent=2, sort_keys=True))
    return 0


def _cmd_load(args: argparse.Namespace) -> int:
    cookies = load_cookies_txt(args.cookies)
    print(f"Loaded {len(cookies)} cookies from {args.cookies}")
    return 0


def _cmd_save(args: argparse.Namespace) -> int:
    cookies = load_cookies_txt(args.input)
    save_cookies_txt(args.output, cookies, atomic=not args.no_atomic)
    print(f"Saved {len(cookies)} cookies to {args.output}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    cookies = load_cookies_txt(args.cookies)
    result = check_required_cookies(
        cookies,
        args.require,
        domain=args.domain,
        allow_subdomains=args.allow_subdomains,
        expiring_soon_seconds=args.expiring_soon_seconds,
    )

    print(f"Checked {len(result.required)} required cookies in {args.cookies}")

    if result.missing:
        print("Missing:", ", ".join(result.missing))
    if result.expired:
        print("Expired:", ", ".join(result.expired))
    if result.expiring_soon:
        print("Expiring soon:", ", ".join(result.expiring_soon))

    if result.ok:
        print("OK")
        return 0
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cookiekit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_spec = subparsers.add_parser(
        "parse-spec",
        help="Parse a browser specification string.",
    )
    parse_spec.add_argument("spec", help="BROWSER[/DOMAIN][+KEYRING][:PROFILE][::CONTAINER]")
    parse_spec.set_defaults(func=_cmd_parse_spec)

    load = subparsers.add_parser(
        "load",
        help="Load a Netscape cookies.txt file and print a summary.",
    )
    load.add_argument("cookies", help="Path to cookies.txt")
    load.set_defaults(func=_cmd_load)

    save = subparsers.add_parser(
        "save",
        help="Load cookies from input file and write to output file.",
    )
    save.add_argument("--input", required=True, help="Input cookies.txt path")
    save.add_argument("--output", required=True, help="Output cookies.txt path")
    save.add_argument(
        "--no-atomic",
        action="store_true",
        help="Write directly to output file instead of temp-file replace.",
    )
    save.set_defaults(func=_cmd_save)

    check = subparsers.add_parser(
        "check",
        help="Check presence and freshness of required cookies.",
    )
    check.add_argument("cookies", help="Path to cookies.txt")
    check.add_argument(
        "--require",
        action="append",
        required=True,
        help="Required cookie name (repeat for multiple names)",
    )
    check.add_argument("--domain", help="Restrict matching to a domain")
    check.add_argument(
        "--allow-subdomains",
        action="store_true",
        help="Allow matching cookies set on subdomains of --domain",
    )
    check.add_argument(
        "--expiring-soon-seconds",
        type=int,
        default=24 * 60 * 60,
        help="Warn for cookies expiring in less than this many seconds",
    )
    check.set_defaults(func=_cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
