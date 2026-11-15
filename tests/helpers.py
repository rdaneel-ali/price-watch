from typing import Any

from price_watch.models import Source, Watch

NOW = "2026-11-14T14:00:00Z"


def make_watch(
    watch_id: str = "w1",
    urls: tuple[str, ...] = ("https://a.example.com/",),
    *,
    target: int = 150_000,
    spec: str = "Mac mini 32GB",
    manual: dict[str, Any] | None = None,
) -> Watch:
    sources = tuple(
        Source(source_id=f"s{i}", name=f"Shop {i}", url=url) for i, url in enumerate(urls)
    )
    return Watch.model_validate(
        {
            "watch_id": watch_id,
            "user_id": "u1",
            "name": "Mac mini",
            "spec": spec,
            "target_price": target,
            "sources": [source.model_dump() for source in sources],
            "manual_price": manual,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )
