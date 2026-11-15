from price_watch.grouping import group_source_urls
from price_watch.models import Source, Watch

NOW = "2026-11-14T14:00:00Z"


def make_watch(
    watch_id: str, urls: list[str], *, enabled: bool = True, disabled: frozenset[str] = frozenset()
) -> Watch:
    sources = tuple(
        Source(source_id=f"s{i}", name=f"n{i}", url=url, enabled=url not in disabled)
        for i, url in enumerate(urls)
    )
    return Watch(
        watch_id=watch_id,
        user_id="u",
        name=watch_id,
        spec="spec",
        target_price=100,
        sources=sources,
        enabled=enabled,
        created_at=NOW,
        updated_at=NOW,
    )


def test_distinct_urls_shared_across_watches() -> None:
    a = make_watch("a", ["https://x.example.com", "https://y.example.com"])
    b = make_watch("b", ["https://y.example.com"])
    grouping = group_source_urls([a, b])
    assert [g.url for g in grouping.selected] == ["https://x.example.com", "https://y.example.com"]
    assert [u.watch.watch_id for u in grouping.selected[1].uses] == ["a", "b"]


def test_skips_disabled_watches_and_sources() -> None:
    a = make_watch(
        "a",
        ["https://x.example.com", "https://y.example.com"],
        disabled=frozenset({"https://y.example.com"}),
    )
    b = make_watch("b", ["https://z.example.com"], enabled=False)
    assert [g.url for g in group_source_urls([a, b]).selected] == ["https://x.example.com"]


def test_extra_urls_are_skipped() -> None:
    watches = [make_watch(f"w{i}", [f"https://h{i}.example.com"]) for i in range(10)]
    grouping = group_source_urls(watches, max_urls=8)
    assert len(grouping.selected) == 8
    assert [g.url for g in grouping.skipped] == ["https://h8.example.com", "https://h9.example.com"]
