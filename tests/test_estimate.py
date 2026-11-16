import pytest

from price_watch.config import LIMITS, MODEL
from price_watch.estimate import estimate_worst_case, format_cents, format_dollars


def test_worst_case_is_characters_plus_max_output() -> None:
    estimate = estimate_worst_case(10_000)
    assert estimate.input_tokens == 10_000
    assert estimate.output_tokens == LIMITS.max_output_tokens
    expected = (
        10_000 * MODEL.input_micro_dollars_per_million_tokens
        + LIMITS.max_output_tokens * MODEL.output_micro_dollars_per_million_tokens
    ) // 1_000_000
    assert estimate.cost_micro_dollars == expected


def test_rounds_up_never_down() -> None:
    assert (
        estimate_worst_case(1).cost_micro_dollars >= estimate_worst_case(0).cost_micro_dollars + 1
    )


def test_negative_characters_raise() -> None:
    with pytest.raises(ValueError):
        estimate_worst_case(-1)


def test_format_dollars() -> None:
    assert format_dollars(100_000) == "$0.100000"


def test_format_dollars_is_exact_for_large_amounts() -> None:
    assert format_dollars(0) == "$0.000000"
    assert format_dollars(9_007_199_254_740_993) == "$9007199254.740993"
    with pytest.raises(ValueError):
        format_dollars(-1)


def test_format_cents() -> None:
    assert format_cents(135_900) == "$1,359.00"
    assert format_cents(5) == "$0.05"
    assert format_cents(9_007_199_254_740_993) == "$90,071,992,547,409.93"
    with pytest.raises(ValueError):
        format_cents(-1)
