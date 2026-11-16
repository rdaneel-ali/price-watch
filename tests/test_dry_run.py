from pathlib import Path

import httpx
import pytest

from price_watch.cli import main
from price_watch.models import Source, Watch
from price_watch.store import JsonFileStore

NOW = "2026-11-14T14:00:00Z"


def make_store(tmp_path: Path) -> JsonFileStore:
    store = JsonFileStore(tmp_path / "s.json")
    sources = tuple(
        Source(source_id=f"s{i}", name=f"n{i}", url=f"https://h{i}.example.com/") for i in range(3)
    )
    store.put_watch(
        Watch(
            watch_id="w1",
            user_id="u",
            name="n",
            spec="Mac mini 32GB",
            target_price=100,
            sources=sources,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    return store


def handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "h0.example.com":
        return httpx.Response(
            200, text="<p>Mac mini $1,000</p>", headers={"content-type": "text/html"}
        )
    if host == "h1.example.com":
        return httpx.Response(500)
    return httpx.Response(200, text="<script>x</script>", headers={"content-type": "text/html"})


def test_dry_run_reports_each_source_and_total(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["check", "w1", "--dry-run"],
        store=make_store(tmp_path),
        transport=httpx.MockTransport(handler),
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "ok" in out and "fetch_failed" in out and "too_large" in out
    assert "worst case $" in out
    assert "no AI call made" in out


def test_unknown_watch_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "nope", "--dry-run"], store=make_store(tmp_path)) == 1
    assert "no watch" in capsys.readouterr().err
