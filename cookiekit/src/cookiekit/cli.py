"""CLI for cookiekit V1."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict

from .browser import BrowserExportResult, export_browser_cookies
from .checks import check_required_cookies
from .cookiestxt import load_cookies_txt, save_cookies_txt
from .selectors import load_rotate_index, save_rotate_index, select_source
from .spec import BrowserSpec, SUPPORTED_BROWSERS, parse_browser_spec
from .sources import load_source, parse_source, resolve_update_target


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


def _build_export_browser_spec(args: argparse.Namespace) -> BrowserSpec:
    if args.spec:
        extras = {
            "--domain": args.domain,
            "--profile": args.profile,
            "--keyring": args.keyring,
            "--container": args.container,
        }
        used = [name for name, value in extras.items() if value]
        if used:
            names = ", ".join(used)
            raise ValueError(f"--spec cannot be combined with {names}")
        return parse_browser_spec(args.spec)

    return BrowserSpec(
        browser=args.browser,
        profile=args.profile,
        keyring=args.keyring,
        container=args.container,
        domain=args.domain,
    )


def _emit_export_browser_result(result: BrowserExportResult, *, as_json: bool) -> None:
    payload = {
        "browser": result.spec.browser,
        "profile": result.spec.profile,
        "keyring": result.spec.keyring,
        "container": result.spec.container,
        "domain": result.spec.domain,
        "output": str(result.output),
        "cookie_count": result.cookie_count,
    }
    if result.chromium_decryption is not None:
        payload["chromium_decryption"] = result.chromium_decryption

    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(f"Exported {result.cookie_count} cookies to {result.output}")
    print(f"Browser: {result.spec.browser}")
    if result.spec.profile:
        print(f"Profile: {result.spec.profile}")
    if result.spec.container:
        print(f"Container: {result.spec.container}")
    if result.spec.domain:
        print(f"Domain filter: {result.spec.domain}")
    if result.chromium_decryption is not None:
        stats = result.chromium_decryption
        print("Chromium decryption stats:", json.dumps(stats, sort_keys=True))
        if stats.get("failed", 0):
            print(f"Warning: skipped {stats['failed']} encrypted cookies that could not be decrypted")


def _cmd_export_browser(args: argparse.Namespace) -> int:
    try:
        spec = _build_export_browser_spec(args)
        result = export_browser_cookies(spec, args.output, atomic=not args.no_atomic)
    except Exception as exc:
        print(f"Browser export error: {exc}")
        return 2

    _emit_export_browser_result(result, as_json=args.json)
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    sources = [parse_source(value) for value in args.source]

    rotate_index = 0
    if args.select == "rotate":
        rotate_index = load_rotate_index(args.rotate_state_file)

    rng = random.Random(args.random_seed) if args.random_seed is not None else None
    selected, next_rotate_index = select_source(
        sources,
        mode=args.select,
        rotate_index=rotate_index,
        rng=rng,
    )

    try:
        loaded = load_source(selected)
    except Exception as exc:
        print(f"Source error: {exc}")
        return 2

    if args.select == "rotate":
        save_rotate_index(args.rotate_state_file, next_rotate_index)

    print(f"Selected source: {selected.kind}:{selected.value}")
    print(f"Loaded {len(loaded.cookies)} cookies")

    update_target = resolve_update_target(args.cookies_update, loaded)
    if update_target:
        save_cookies_txt(update_target, loaded.cookies, atomic=not args.no_atomic)
        print(f"Updated cookies at: {update_target}")
    else:
        print("cookies-update is off or no update target resolved")

    return 0


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

    export_browser = subparsers.add_parser(
        "export-browser",
        help="Load cookies directly from a logged-in browser profile and write cookies.txt.",
    )
    export_input = export_browser.add_mutually_exclusive_group(required=True)
    export_input.add_argument(
        "--spec",
        help="Full browser spec: BROWSER[/DOMAIN][+KEYRING][:PROFILE][::CONTAINER]",
    )
    export_input.add_argument(
        "--browser",
        choices=tuple(sorted(SUPPORTED_BROWSERS)),
        help="Browser family when passing profile/domain/container as separate flags.",
    )
    export_browser.add_argument(
        "--profile",
        help="Browser profile name or path. Omit to auto-pick the most recently used profile.",
    )
    export_browser.add_argument(
        "--domain",
        help="Optional domain filter. Use .example.com to include subdomains.",
    )
    export_browser.add_argument(
        "--keyring",
        help="Optional Chromium keyring override: kwallet|gnomekeyring|basictext",
    )
    export_browser.add_argument(
        "--container",
        help="Optional Firefox container name. Use 'all' for all containers.",
    )
    export_browser.add_argument(
        "-o",
        "--output",
        "--cookies-export",
        required=True,
        help="Output cookies.txt path",
    )
    export_browser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON summary instead of plain text.",
    )
    export_browser.add_argument(
        "--no-atomic",
        action="store_true",
        help="Write directly to output file instead of temp-file replace.",
    )
    export_browser.set_defaults(func=_cmd_export_browser)

    sync = subparsers.add_parser(
        "sync",
        aliases=["noop"],
        help="Cookie-only flow: select a source, load cookies, and optionally persist update.",
    )
    sync.add_argument(
        "--source",
        action="append",
        required=True,
        help="Cookie source. File path or browser spec via browser:<SPEC>",
    )
    sync.add_argument(
        "--select",
        choices=("first", "random", "rotate"),
        default="first",
        help="Source selection strategy for multiple --source values",
    )
    sync.add_argument(
        "--rotate-state-file",
        default=".cookiekit.rotate-state.json",
        help="State file used to persist rotate index",
    )
    sync.add_argument(
        "--random-seed",
        type=int,
        help="Optional seed for deterministic random source selection",
    )
    sync.add_argument(
        "--cookies-update",
        default="auto",
        help="Update behavior: auto|off|<path>. auto updates selected file source.",
    )
    sync.add_argument(
        "--no-atomic",
        action="store_true",
        help="Write directly when updating cookies instead of temp-file replace.",
    )
    sync.set_defaults(func=_cmd_sync)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
