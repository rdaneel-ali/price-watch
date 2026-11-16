"""Command-line entry point for the `pw` admin tool."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx

from price_watch.dry_run import format_dry_run, run_dry_run
from price_watch.fetch import make_client
from price_watch.store import JsonFileStore, Store, resolve_store_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pw", description="Price Watch admin tool.")
    commands = parser.add_subparsers(dest="command")
    check = commands.add_parser("check", help="Run a check for one watch.")
    check.add_argument("watch", help="The watch_id.")
    check.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and estimate tokens and cost without calling the AI.",
    )
    return parser


def command_check(
    args: argparse.Namespace, store: Store, transport: httpx.BaseTransport | None
) -> int:
    watch = store.get_watch(args.watch)
    if watch is None:
        print(f"pw: no watch with id {args.watch!r}", file=sys.stderr)
        return 1
    if args.dry_run:
        with make_client(transport) as client:
            print(format_dry_run(run_dry_run(watch, client)))
        return 0
    print("pw: a real check is not available yet; use --dry-run", file=sys.stderr)
    return 1


def main(
    argv: Sequence[str] | None = None,
    *,
    store: Store | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return command_check(args, store or JsonFileStore(Path(resolve_store_path())), transport)
    parser.print_help()
    return 0
