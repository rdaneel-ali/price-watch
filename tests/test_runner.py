import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from price_watch.cli import main
from price_watch.config import LIMITS, MODEL
from price_watch.fetch import make_client
from price_watch.models import SourceStatus
from price_watch.openrouter import make_ai_client
from price_watch.runner import run_check
from price_watch.store import JsonFileStore
from tests.helpers import NOW, make_watch

NOW_DT = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
KEY = "test-key-not-real"


def listing_item(
    price: int, url: str = "https://shop.example.com/1", **extra: object
) -> dict[str, object]:
    return {
        "title": "Mac mini",
        "price_cents": price,
        "condition": "new",
        "url": url,
        "ai_confidence": "high",
        "judgments": [{"watch_id": "w1", "meets_spec": True, "spec_reason": "ok"}],
        **extra,
    }


def user_payload(body: dict[str, object]) -> dict[str, Any]:
    messages: Any = body["messages"]
    payload: dict[str, Any] = json.loads(messages[1]["content"])
    return payload


class FakeWorld:
    """Pages and an OpenRouter stand-in, all in memory. Records the AI requests."""

    def __init__(self, answers: list[object], cost: float | None = 0.0002) -> None:
        self.answers = answers
        self.cost = cost
        self.ai_bodies: list[dict[str, object]] = []
        self.ai_headers: list[httpx.Headers] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "openrouter.ai":
            self.ai_bodies.append(json.loads(request.content))
            self.ai_headers.append(request.headers)
            answer = self.answers[min(len(self.ai_bodies), len(self.answers)) - 1]
            if isinstance(answer, int):
                return httpx.Response(answer)
            usage: dict[str, object] = {"prompt_tokens": 100, "completion_tokens": 50}
            if self.cost is not None:
                usage["cost"] = self.cost
            content = answer if isinstance(answer, str) else json.dumps({"listings": answer})
            return httpx.Response(
                200, json={"choices": [{"message": {"content": content}}], "usage": usage}
            )
        if request.url.host == "bad.example.com":
            return httpx.Response(500)
        return httpx.Response(200, text="<p>Mac mini</p>", headers={"content-type": "text/html"})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


def run(world: FakeWorld, store: JsonFileStore, urls: tuple[str, ...], **watch_args: object):  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType]
    watch = make_watch(urls=urls, **watch_args)  # pyright: ignore[reportArgumentType]
    transport = world.transport()
    with make_client(transport) as fetch_client, make_ai_client(transport) as ai_client:
        return run_check([watch], store, fetch_client, ai_client, KEY, NOW_DT)


def test_end_to_end_stores_check_and_listings(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld([[listing_item(140000), listing_item(160000, "https://shop.example.com/2")]])
    checks = run(world, store, ("https://a.example.com/",))
    assert checks[0].best is not None and checks[0].best.price == 140000
    assert checks[0].sources[0].status is SourceStatus.OK
    stored = store.list_checks("w1")[0]
    assert [item.price for item in stored.listings] == [140000, 160000]
    day = store.get_spend("DAY#2026-11-14")
    assert (day.cost, day.calls, day.input_tokens, day.output_tokens) == (200, 1, 100, 50)


def test_request_is_pinned_no_fallback_capped_and_page_is_data(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld([[]])
    run(world, store, ("https://a.example.com/",))
    body = world.ai_bodies[0]
    assert body["model"] == MODEL.name
    assert body["max_tokens"] == LIMITS.max_output_tokens
    assert body["provider"] == {"allow_fallbacks": False, "require_parameters": True}
    assert "tools" not in body
    assert world.ai_headers[0]["authorization"] == f"Bearer {KEY}"
    user = user_payload(body)
    assert user["page_text"] == "Mac mini"


def test_shared_url_one_call_for_two_watches(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld([[]])
    watches = [make_watch("w1"), make_watch("w2")]
    transport = world.transport()
    with make_client(transport) as fetch_client, make_ai_client(transport) as ai_client:
        run_check(watches, store, fetch_client, ai_client, KEY, NOW_DT)
    assert len(world.ai_bodies) == 1
    sent = user_payload(world.ai_bodies[0])
    assert [w["watch_id"] for w in sent["watches"]] == ["w1", "w2"]


def test_retry_once_then_ai_failed_and_both_attempts_reserved(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld(["garbage", "garbage again"])
    checks = run(world, store, ("https://a.example.com/",))
    assert len(world.ai_bodies) == 2
    assert checks[0].sources[0].status is SourceStatus.AI_FAILED
    assert store.get_spend("DAY#2026-11-14").calls == 2


def test_retry_succeeds(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld(["garbage", [listing_item(100000)]])
    checks = run(world, store, ("https://a.example.com/",))
    assert checks[0].sources[0].status is SourceStatus.OK


def test_failed_call_without_cost_keeps_reservation(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld([500, 500])
    checks = run(world, store, ("https://a.example.com/",))
    assert checks[0].sources[0].status is SourceStatus.AI_FAILED
    assert store.get_spend("DAY#2026-11-14").cost > 1000  # two worst-case reservations stay


def test_fetch_failure_makes_no_ai_call(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld([[]])
    checks = run(world, store, ("https://bad.example.com/",))
    assert checks[0].sources[0].status is SourceStatus.FETCH_FAILED
    assert world.ai_bodies == []


def test_no_listings_status(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    checks = run(FakeWorld([[listing_item(0)]]), store, ("https://a.example.com/",))
    assert checks[0].sources[0].status is SourceStatus.NO_LISTINGS
    assert checks[0].best is None


def test_budget_stops_the_run(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    from price_watch.models import Spend

    store.put_spend(Spend(period="DAY#2026-11-14", cost=99_999))
    world = FakeWorld([[listing_item(100000)]])
    checks = run(world, store, ("https://a.example.com/", "https://b.example.com/"))
    assert [r.status for r in checks[0].sources] == [SourceStatus.BUDGET_STOPPED] * 2
    assert world.ai_bodies == []


def test_manual_price_wins_when_cheapest(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    world = FakeWorld([[listing_item(140000)]])
    manual = {"price": 120000, "set_at": NOW}
    checks = run(world, store, ("https://a.example.com/",), manual=manual)
    assert checks[0].best is not None and checks[0].best.source_id == "manual"


def test_cli_without_key_exits_with_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    store.put_watch(make_watch())
    code = main(["check", "w1"], store=store, environ={})
    assert code == 2
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err


def test_cli_end_to_end_prints_best_and_spend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    store.put_watch(make_watch())
    world = FakeWorld([[listing_item(135900)]])
    code = main(
        ["check", "w1"],
        store=store,
        transport=world.transport(),
        environ={"OPENROUTER_API_KEY": KEY},
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "$1,359.00" in out and "meets target" in out and "Spend today" in out
    assert KEY not in out
