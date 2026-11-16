"""`pw check --dry-run`: fetch and trim, then estimate the worst-case cost. No AI call."""

from dataclasses import dataclass

import httpx

from price_watch.estimate import (
    PROMPT_OVERHEAD_CHARACTERS,
    Estimate,
    estimate_worst_case,
    format_dollars,
)
from price_watch.fetch import FetchError, PageTooLargeError, fetch_url
from price_watch.grouping import UrlGroup, group_source_urls
from price_watch.models import SourceStatus, Watch
from price_watch.trim import trim_page


@dataclass(frozen=True, slots=True)
class DryRunEntry:
    url: str
    status: SourceStatus
    characters: int = 0
    estimate: Estimate | None = None


def fetch_group_text(client: httpx.Client, group: UrlGroup) -> tuple[SourceStatus, str]:
    """Fetch and trim one URL. The text is empty unless the status is OK."""
    try:
        page = fetch_url(client, group.url)
    except PageTooLargeError:
        return SourceStatus.TOO_LARGE, ""
    except FetchError:
        return SourceStatus.FETCH_FAILED, ""
    text = trim_page(page)
    if text is None:
        return SourceStatus.TOO_LARGE, ""
    return SourceStatus.OK, text


def run_dry_run(watch: Watch, client: httpx.Client) -> list[DryRunEntry]:
    grouping = group_source_urls([watch])
    entries: list[DryRunEntry] = []
    for group in grouping.selected:
        status, text = fetch_group_text(client, group)
        if status is not SourceStatus.OK:
            entries.append(DryRunEntry(group.url, status))
            continue
        spec_characters = sum(len(use.watch.spec) for use in group.uses)
        request_characters = PROMPT_OVERHEAD_CHARACTERS + spec_characters + len(text)
        entries.append(
            DryRunEntry(group.url, status, len(text), estimate_worst_case(request_characters))
        )
    entries.extend(DryRunEntry(group.url, SourceStatus.SKIPPED) for group in grouping.skipped)
    return entries


def format_dry_run(entries: list[DryRunEntry]) -> str:
    lines: list[str] = []
    total = 0
    for entry in entries:
        if entry.estimate is None:
            lines.append(f"{entry.status.value:<13} {entry.url}")
            continue
        total += entry.estimate.cost_micro_dollars
        lines.append(
            f"{entry.status.value:<13} {entry.url}\n"
            f"              {entry.characters} chars, {entry.estimate.input_tokens} input tokens,"
            f" {entry.estimate.output_tokens} output tokens max,"
            f" worst case {format_dollars(entry.estimate.cost_micro_dollars)}"
        )
    lines.append(f"Worst-case total: {format_dollars(total)} (no AI call made)")
    return "\n".join(lines)
