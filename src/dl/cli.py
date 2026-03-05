"""Top-level CLI wrapper for the workspace tools."""

from __future__ import annotations

import argparse

from cookiekit.cli import main as cookiekit_main
from downloadkit.cli import main as downloadkit_main
from requestkit.cli import main as requestkit_main

TOOLS = {
    "cookiekit": cookiekit_main,
    "requestkit": requestkit_main,
    "downloadkit": downloadkit_main,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dl",
        description="Top-level wrapper for cookiekit, requestkit, and downloadkit.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="dl 0.1.0",
    )
    parser.add_argument(
        "tool",
        nargs="?",
        choices=tuple(sorted(TOOLS)),
        help="Tool to run.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the selected tool.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(argv)

    if parsed.tool is None:
        parser.print_help()
        return 0

    tool_args = parsed.args or ["--help"]
    return TOOLS[parsed.tool](tool_args)
