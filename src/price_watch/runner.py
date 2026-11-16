"""A check run: group, fetch, extract under the budget, judge, store."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from price_watch.budget import BudgetExceededError, SpendLedger
from price_watch.config import HISTORY_DAYS, LIMITS
from price_watch.dry_run import fetch_group_text
from price_watch.estimate import estimate_worst_case
from price_watch.extraction import ExtractedListing, ExtractionError, parse_extraction
from price_watch.grouping import UrlGroup, group_source_urls
from price_watch.judging import (
    flag_suspicious,
    make_ai_listing,
    make_manual_listing,
    pick_best,
)
from price_watch.models import Check, Listing, SourceResult, SourceStatus, Watch
from price_watch.openrouter import ChatResult, OpenRouterError, call_chat
from price_watch.prompt import build_request_body, count_request_characters
from price_watch.store import Store
from price_watch.timeutil import format_utc, parse_utc

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GroupOutcome:
    status: SourceStatus
    listings: tuple[ExtractedListing, ...] = ()


class AiFailedError(Exception):
    """Every attempt failed or gave an answer that did not match the shape."""


def extract_group(
    ai_client: httpx.Client, api_key: str, ledger: SpendLedger, group: UrlGroup, page_text: str
) -> list[ExtractedListing]:
    """One AI call per URL, plus at most one retry. Every attempt reserves the worst case
    first; BudgetExceededError propagates to stop the run."""
    watch_specs = [(use.watch.watch_id, use.watch.spec) for use in group.uses]
    watch_ids = [watch_id for watch_id, _ in watch_specs]
    body = build_request_body(group.url, page_text, watch_specs)
    worst_case = estimate_worst_case(count_request_characters(body)).cost_micro_dollars
    for _ in range(1 + LIMITS.max_retries):
        reservation = ledger.reserve(worst_case)
        try:
            result: ChatResult = call_chat(ai_client, api_key, body)
        except OpenRouterError as error:
            ledger.settle(reservation, error.usage)
            logger.warning("AI call failed for %s: %s", group.url, error)
            continue
        ledger.settle(reservation, result.usage)
        try:
            return parse_extraction(result.content, watch_ids)
        except ExtractionError as error:
            logger.warning("AI answer rejected for %s: %s", group.url, error)
    raise AiFailedError(group.url)


def process_group(
    fetch_client: httpx.Client,
    ai_client: httpx.Client,
    api_key: str,
    ledger: SpendLedger,
    group: UrlGroup,
) -> GroupOutcome:
    """Fetch, trim and extract one URL. BudgetExceededError propagates."""
    status, page_text = fetch_group_text(fetch_client, group)
    if status is not SourceStatus.OK:
        return GroupOutcome(status)
    try:
        listings = extract_group(ai_client, api_key, ledger, group, page_text)
    except AiFailedError:
        return GroupOutcome(SourceStatus.AI_FAILED)
    if not listings:
        return GroupOutcome(SourceStatus.NO_LISTINGS)
    return GroupOutcome(SourceStatus.OK, tuple(listings))


def collect_outcomes(
    fetch_client: httpx.Client,
    ai_client: httpx.Client,
    api_key: str,
    ledger: SpendLedger,
    watches: Sequence[Watch],
) -> dict[str, GroupOutcome]:
    grouping = group_source_urls(watches)
    outcomes: dict[str, GroupOutcome] = {}
    stopped = False
    for group in grouping.selected:
        if stopped:
            outcomes[group.url] = GroupOutcome(SourceStatus.BUDGET_STOPPED)
            continue
        try:
            outcomes[group.url] = process_group(fetch_client, ai_client, api_key, ledger, group)
        except BudgetExceededError:
            stopped = True
            outcomes[group.url] = GroupOutcome(SourceStatus.BUDGET_STOPPED)
    for group in grouping.skipped:
        outcomes[group.url] = GroupOutcome(SourceStatus.SKIPPED)
    return outcomes


def history_best_prices(store: Store, watch_id: str, now: datetime) -> list[int]:
    since = now - timedelta(days=HISTORY_DAYS)
    return [
        stored.check.best.price
        for stored in store.list_checks(watch_id)
        if stored.check.best is not None and parse_utc(stored.check.checked_at) >= since
    ]


def build_watch_check(
    watch: Watch, outcomes: dict[str, GroupOutcome], store: Store, now: datetime
) -> tuple[Check, list[Listing]]:
    timestamp = format_utc(now)
    results: list[SourceResult] = []
    listings: list[Listing] = []
    for source in watch.sources:
        if not source.enabled:
            continue
        outcome = outcomes[source.url]
        results.append(
            SourceResult(
                source_id=source.source_id,
                status=outcome.status,
                listing_count=len(outcome.listings),
            )
        )
        listings.extend(
            make_ai_listing(watch, source.source_id, extracted, timestamp)
            for extracted in outcome.listings
        )
    manual = make_manual_listing(watch)
    if manual is not None:
        listings.append(manual)
    listings = flag_suspicious(listings, history_best_prices(store, watch.watch_id, now))
    listings.sort(key=lambda listing: listing.price)
    check = Check(
        watch_id=watch.watch_id,
        user_id=watch.user_id,
        checked_at=timestamp,
        sources=tuple(results),
        best=pick_best(listings),
    )
    return check, listings


def run_check(
    watches: Sequence[Watch],
    store: Store,
    fetch_client: httpx.Client,
    ai_client: httpx.Client,
    api_key: str,
    now: datetime,
) -> list[Check]:
    """Check the enabled watches given, storing each check with its listings."""
    enabled = [watch for watch in watches if watch.enabled]
    ledger = SpendLedger(store, now)
    outcomes = collect_outcomes(fetch_client, ai_client, api_key, ledger, enabled)
    checks: list[Check] = []
    for watch in enabled:
        check, listings = build_watch_check(watch, outcomes, store, now)
        store.save_check(check, listings)
        checks.append(check)
    return checks
