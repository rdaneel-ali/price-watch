"""Worst-case token and cost estimates. Same rule as the budget reservation:
1 token per character of the full request, plus the maximum output tokens."""

from dataclasses import dataclass

from price_watch.config import CENTS_PER_DOLLAR, LIMITS, MICRO_DOLLARS_PER_DOLLAR, MODEL

TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True, slots=True)
class Estimate:
    input_tokens: int
    output_tokens: int
    cost_micro_dollars: int


def ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def estimate_worst_case(request_characters: int) -> Estimate:
    if request_characters < 0:
        raise ValueError("request_characters must not be negative")
    output_tokens = LIMITS.max_output_tokens
    cost = ceil_div(
        request_characters * MODEL.input_micro_dollars_per_million_tokens, TOKENS_PER_MILLION
    ) + ceil_div(output_tokens * MODEL.output_micro_dollars_per_million_tokens, TOKENS_PER_MILLION)
    return Estimate(request_characters, output_tokens, cost)


def format_dollars(micro_dollars: int) -> str:
    """Micro-dollars as `$0.100000`, in integer arithmetic."""
    if micro_dollars < 0:
        raise ValueError("micro_dollars must not be negative")
    dollars, rest = divmod(micro_dollars, MICRO_DOLLARS_PER_DOLLAR)
    return f"${dollars}.{rest:06d}"


def format_cents(cents: int) -> str:
    """Cents as `$1,359.00`, in integer arithmetic."""
    if cents < 0:
        raise ValueError("cents must not be negative")
    dollars, rest = divmod(cents, CENTS_PER_DOLLAR)
    return f"${dollars:,}.{rest:02d}"
