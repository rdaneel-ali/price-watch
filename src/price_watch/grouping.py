"""Group the enabled source URLs across watches so each URL is fetched once per run."""

from collections.abc import Iterable
from dataclasses import dataclass

from price_watch.config import LIMITS
from price_watch.models import Source, Watch


@dataclass(frozen=True, slots=True)
class SourceUse:
    watch: Watch
    source: Source


@dataclass(frozen=True, slots=True)
class UrlGroup:
    url: str
    uses: tuple[SourceUse, ...]


@dataclass(frozen=True, slots=True)
class Grouping:
    selected: tuple[UrlGroup, ...]
    skipped: tuple[UrlGroup, ...]


def group_source_urls(
    watches: Iterable[Watch], max_urls: int = LIMITS.max_urls_per_run
) -> Grouping:
    """Distinct enabled URLs in first-seen order; those past `max_urls` are skipped."""
    uses_by_url: dict[str, list[SourceUse]] = {}
    for watch in watches:
        if not watch.enabled:
            continue
        for source in watch.sources:
            if source.enabled:
                uses_by_url.setdefault(source.url, []).append(SourceUse(watch, source))
    groups = [UrlGroup(url, tuple(uses)) for url, uses in uses_by_url.items()]
    return Grouping(selected=tuple(groups[:max_urls]), skipped=tuple(groups[max_urls:]))
