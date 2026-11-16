import json

import pytest

from price_watch.extraction import ExtractionError, parse_extraction
from price_watch.openrouter import OpenRouterError, dollars_to_micro, parse_chat_response


def item(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Mac mini",
        "price_cents": 135900,
        "condition": "refurbished",
        "url": "https://example.com/l",
        "ai_confidence": "high",
        "judgments": [{"watch_id": "w1", "meets_spec": True, "spec_reason": "ok"}],
    }
    return {**base, **overrides}


def answer(*items: dict[str, object]) -> str:
    return json.dumps({"listings": list(items)})


def test_valid_answer() -> None:
    listings = parse_extraction(answer(item()), ["w1"])
    assert listings[0].price_cents == 135900


def test_empty_listings_is_valid() -> None:
    assert parse_extraction(answer(), ["w1"]) == []


@pytest.mark.parametrize(
    "bad",
    [
        item(price_cents=None),
        item(price_cents=0),
        item(price_cents=-5),
        item(price_cents=True),
        item(price_cents="100"),
        item(url=None),
        item(url="http://example.com/l"),
        item(url="/relative"),
    ],
)
def test_listings_without_price_or_https_url_are_dropped(bad: dict[str, object]) -> None:
    assert parse_extraction(answer(bad, item()), ["w1"]) == parse_extraction(answer(item()), ["w1"])


def test_drop_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    parse_extraction(answer(item(price_cents=0)), ["w1"])
    assert "dropped" in caplog.text


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"items": []}',
        '{"listings": [1]}',
        answer(item(condition="mint")),
        answer(item(ai_confidence="sure")),
        answer(item(judgments=[])),
        answer(item(judgments=[{"watch_id": "other", "meets_spec": True, "spec_reason": "x"}])),
        answer(item(title=None)),
    ],
)
def test_bad_shape_raises(content: str) -> None:
    with pytest.raises(ExtractionError):
        parse_extraction(content, ["w1"])


def test_judges_every_watch() -> None:
    both = item(
        judgments=[
            {"watch_id": "w1", "meets_spec": True, "spec_reason": "a"},
            {"watch_id": "w2", "meets_spec": False, "spec_reason": "b"},
        ]
    )
    assert len(parse_extraction(answer(both), ["w1", "w2"])) == 1
    with pytest.raises(ExtractionError):
        parse_extraction(answer(item()), ["w1", "w2"])


def test_cost_converts_to_micro_dollars_rounding_up() -> None:
    assert dollars_to_micro(0.000123) == 123
    assert dollars_to_micro(0.0000001) == 1
    assert dollars_to_micro(0) == 0
    assert dollars_to_micro(-1) is None


def test_parse_chat_response_reads_usage_and_cost() -> None:
    result = parse_chat_response(
        {
            "choices": [{"message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.00042},
        }
    )
    assert (result.content, result.usage.input_tokens, result.usage.cost_micro_dollars) == (
        "{}",
        10,
        420,
    )


def test_parse_chat_response_without_cost_or_choices() -> None:
    result = parse_chat_response({"usage": {"prompt_tokens": 1}})
    assert result.content == "" and result.usage.cost_micro_dollars is None
    with pytest.raises(OpenRouterError):
        parse_chat_response("nope")
