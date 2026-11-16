import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from price_watch.config import CAPS, LIMITS, MODEL
from price_watch.models import (
    BestResponse,
    Check,
    ContractListing,
    Listing,
    ListingsResponse,
    ManualPrice,
    Source,
    SourceResult,
    SourceStatus,
    Spend,
    Watch,
    WatchListItem,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOW = "2026-11-14T14:00:00Z"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def dump(model: BaseModel) -> Any:
    return model.model_dump(mode="json")


def test_watches_fixture_round_trips() -> None:
    raw = load_fixture("watches.json")
    assert [dump(WatchListItem.model_validate(item)) for item in raw] == raw


def test_best_fixture_round_trips() -> None:
    raw = load_fixture("best.json")
    assert dump(BestResponse.model_validate(raw)) == raw


def test_listings_fixture_round_trips() -> None:
    raw = load_fixture("listings.json")
    assert dump(ListingsResponse.model_validate(raw)) == raw


def test_best_allows_null_best_and_checked_at() -> None:
    raw = {**load_fixture("best.json"), "checked_at": None, "best": None, "check_ok": False}
    assert dump(BestResponse.model_validate(raw)) == raw


@pytest.mark.parametrize("bad", ["2026-11-14T14:00:00", "2026-11-14T14:00:00+00:00", "yesterday"])
def test_timestamp_needs_trailing_z(bad: str) -> None:
    raw = {**load_fixture("best.json"), "checked_at": bad}
    with pytest.raises(ValidationError):
        BestResponse.model_validate(raw)


@pytest.mark.parametrize(
    "bad",
    [
        "2026-02-29T14:00:00Z",
        "2026-02-30T14:00:00Z",
        "2026-11-14T25:00:00Z",
        "2026-11-14T14:61:00Z",
    ],
)
def test_timestamp_must_be_a_real_date_and_time(bad: str) -> None:
    raw = {**load_fixture("best.json"), "checked_at": bad}
    with pytest.raises(ValidationError):
        BestResponse.model_validate(raw)


def test_timestamp_keeps_its_original_text() -> None:
    raw = {**load_fixture("best.json"), "checked_at": "2026-11-14T14:00:00.123Z"}
    assert BestResponse.model_validate(raw).checked_at == "2026-11-14T14:00:00.123Z"


def test_contract_url_null_only_for_manual() -> None:
    raw = load_fixture("best.json")["best"]
    with pytest.raises(ValidationError):
        ContractListing.model_validate({**raw, "url": None})
    manual = {**raw, "source_name": "Manual"}
    assert ContractListing.model_validate(manual).url == raw["url"]
    assert ContractListing.model_validate({**manual, "url": None}).url is None


@pytest.mark.parametrize("bad", ["http://example.com/a", "/relative", "https://", "ftp://x.com"])
def test_contract_url_must_be_absolute_https(bad: str) -> None:
    raw = load_fixture("best.json")["best"]
    with pytest.raises(ValidationError):
        ContractListing.model_validate({**raw, "url": bad})


def make_listing(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Mac mini",
        "price": 100000,
        "condition": "new",
        "url": "https://example.com/a",
        "source_id": "s1",
        "meets_spec": True,
        "spec_reason": "ok",
        "ai_confidence": "high",
        "meets_target": True,
        "suspicious": False,
        "status": "found",
        "seen_at": NOW,
    }
    return {**base, **overrides}


def test_listing_price_must_be_positive() -> None:
    for price in (0, -5):
        with pytest.raises(ValidationError):
            Listing.model_validate(make_listing(price=price))


@pytest.mark.parametrize("bad", [True, 100000.0, "100000"])
def test_listing_price_must_be_a_real_int(bad: object) -> None:
    with pytest.raises(ValidationError):
        Listing.model_validate(make_listing(price=bad))


def test_ai_listing_needs_url_and_confidence() -> None:
    with pytest.raises(ValidationError):
        Listing.model_validate(make_listing(url=None))
    with pytest.raises(ValidationError):
        Listing.model_validate(make_listing(ai_confidence=None))


def test_manual_listing_may_omit_url_and_confidence() -> None:
    listing = Listing.model_validate(
        make_listing(source_id="manual", url=None, ai_confidence=None, status="confirmed")
    )
    assert listing.url is None


def test_manual_listing_is_never_suspicious() -> None:
    with pytest.raises(ValidationError):
        Listing.model_validate(
            make_listing(source_id="manual", ai_confidence=None, suspicious=True)
        )


def make_watch(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "watch_id": "w_01",
        "user_id": "u_1",
        "name": "Mac mini",
        "spec": "Mac mini 32GB",
        "target_price": 149900,
        "sources": [
            {"source_id": "s1", "name": "A", "url": "https://a.example.com"},
            {"source_id": "s2", "name": "B", "url": "https://b.example.com"},
        ],
        "created_at": NOW,
        "updated_at": NOW,
    }
    return {**base, **overrides}


def test_watch_valid_and_defaults() -> None:
    watch = Watch.model_validate(make_watch())
    assert watch.enabled is True
    assert watch.manual_price is None


def test_watch_rejects_non_positive_target() -> None:
    with pytest.raises(ValidationError):
        Watch.model_validate(make_watch(target_price=0))


def test_watch_allows_at_most_five_sources() -> None:
    sources = [
        {"source_id": f"s{i}", "name": "n", "url": f"https://e{i}.example.com"} for i in range(6)
    ]
    with pytest.raises(ValidationError):
        Watch.model_validate(make_watch(sources=sources))


def test_watch_rejects_duplicate_and_reserved_source_ids() -> None:
    dup = [{"source_id": "s1", "name": "n", "url": "https://a.example.com"}] * 2
    with pytest.raises(ValidationError):
        Watch.model_validate(make_watch(sources=dup))
    reserved = [{"source_id": "manual", "name": "n", "url": "https://a.example.com"}]
    with pytest.raises(ValidationError):
        Watch.model_validate(make_watch(sources=reserved))


@pytest.mark.parametrize("reserved", ["Manual", "manual", " MANUAL "])
def test_source_name_manual_is_reserved(reserved: str) -> None:
    with pytest.raises(ValidationError):
        Source.model_validate({"source_id": "s", "name": reserved, "url": "https://a.example.com"})


def test_source_rejects_http_url() -> None:
    with pytest.raises(ValidationError):
        Source.model_validate({"source_id": "s", "name": "n", "url": "http://a.example.com"})


def test_manual_price_optional_fields() -> None:
    price = ManualPrice.model_validate({"price": 5000, "set_at": NOW})
    assert price.url is None and price.note is None


def test_check_with_source_statuses() -> None:
    check = Check(
        watch_id="w_01",
        user_id="u_1",
        checked_at=NOW,
        sources=(
            SourceResult(source_id="s1", status=SourceStatus.OK, listing_count=3),
            SourceResult(source_id="s2", status=SourceStatus.BUDGET_STOPPED),
        ),
    )
    assert check.best is None
    assert check.sources[1].listing_count == 0


def test_check_needs_user_id() -> None:
    with pytest.raises(ValidationError):
        Check.model_validate({"watch_id": "w_01", "checked_at": NOW, "sources": []})
    with pytest.raises(ValidationError):
        Check.model_validate({"watch_id": "w_01", "user_id": "", "checked_at": NOW, "sources": []})


def test_spend_period_format() -> None:
    assert Spend(period="DAY#2026-11-14").cost == 0
    assert Spend(period="MONTH#2026-11").calls == 0
    with pytest.raises(ValidationError):
        Spend(period="WEEK#2026-11")
    with pytest.raises(ValidationError):
        Spend(period="DAY#2026-11-14", cost=-1)


@pytest.mark.parametrize("field", ["cost", "calls", "input_tokens", "output_tokens"])
def test_spend_counts_must_be_real_ints(field: str) -> None:
    for bad in (True, 1.0, "1"):
        with pytest.raises(ValidationError):
            Spend.model_validate({"period": "DAY#2026-11-14", field: bad})


def test_config_values() -> None:
    assert MODEL.name == "deepseek/deepseek-v4.1-flash"
    assert CAPS.daily_micro_dollars == 100_000
    assert CAPS.monthly_micro_dollars == 1_500_000
    assert LIMITS.max_urls_per_run == 8
    assert LIMITS.max_response_bytes == 2 * 1024 * 1024
    assert LIMITS.max_output_tokens == 4_000
    assert LIMITS.freshness_hours == 48
