"""Command-line entry point for the `pw` admin tool."""

import argparse
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from price_watch.budget import SpendLedger
from price_watch.config import API_KEY_ENV, CAPS
from price_watch.dry_run import format_dry_run, run_dry_run
from price_watch.env import load_env_file
from price_watch.estimate import format_dollars
from price_watch.fetch import make_client
from price_watch.models import Check
from price_watch.openrouter import make_ai_client
from price_watch.runner import run_check
from price_watch.store import JsonFileStore, Store, resolve_store_path

ENV_FILE = Path(".env")


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


def format_check(check: Check) -> str:
    lines = [f"Checked {check.watch_id} at {check.checked_at}"]
    lines.extend(
        f"  {result.source_id}: {result.status.value} ({result.listing_count} listings)"
        for result in check.sources
    )
    best = check.best
    if best is None:
        lines.append("  Best: nothing meets the spec")
    else:
        flag = " [SUSPICIOUS: " + (best.suspicious_reason or "") + "]" if best.suspicious else ""
        target = "meets target" if best.meets_target else "above target"
        lines.append(f"  Best: ${best.price / 100:,.2f} ({target}) {best.title}{flag}")
    return "\n".join(lines)


def format_spend(store: Store, now: datetime) -> str:
    day, month = SpendLedger(store, now).current()
    return (
        f"Spend today {format_dollars(day.cost)} of {format_dollars(CAPS.daily_micro_dollars)}, "
        f"month {format_dollars(month.cost)} of {format_dollars(CAPS.monthly_micro_dollars)}"
    )


def command_check(
    args: argparse.Namespace,
    store: Store,
    transport: httpx.BaseTransport | None,
    environ: Mapping[str, str],
) -> int:
    watch = store.get_watch(args.watch)
    if watch is None:
        print(f"pw: no watch with id {args.watch!r}", file=sys.stderr)
        return 1
    if args.dry_run:
        with make_client(transport) as client:
            print(format_dry_run(run_dry_run(watch, client)))
        return 0
    api_key = environ.get(API_KEY_ENV)
    if not api_key:
        print(
            f"pw: {API_KEY_ENV} is not set. Put it in a local .env file or export it.",
            file=sys.stderr,
        )
        return 2
    now = datetime.now(UTC)
    with make_client(transport) as fetch_client, make_ai_client(transport) as ai_client:
        checks = run_check([watch], store, fetch_client, ai_client, api_key, now)
    print("\n".join(format_check(check) for check in checks))
    print(format_spend(store, now))
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    store: Store | None = None,
    transport: httpx.BaseTransport | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    logging.basicConfig(level=logging.WARNING, format="pw: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "check":
        parser.print_help()
        return 0
    if environ is None:
        load_env_file(ENV_FILE)
        environ = os.environ
    return command_check(args, store or JsonFileStore(resolve_store_path()), transport, environ)
