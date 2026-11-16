"""Model, prices, caps and limits in one place, so any change shows up in a PR review."""

from dataclasses import dataclass

MICRO_DOLLARS_PER_DOLLAR = 1_000_000
CENTS_PER_DOLLAR = 100


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """The pinned model and its prices, in micro-dollars per million tokens.

    PLACEHOLDER PRICES: OpenRouter lists several providers for this model with different
    prices ($0.05 to $3 input per million tokens). These are the common mid-range rates
    ($0.30 input, $1.20 output) and are unconfirmed. Verify against the public model page
    before relying on cost estimates. Real costs come from OpenRouter's response.
    """

    name: str
    input_micro_dollars_per_million_tokens: int
    output_micro_dollars_per_million_tokens: int


@dataclass(frozen=True, slots=True)
class Caps:
    """Hard spend caps, in micro-dollars."""

    daily_micro_dollars: int
    monthly_micro_dollars: int


@dataclass(frozen=True, slots=True)
class Limits:
    max_urls_per_run: int
    fetch_timeout_seconds: float
    ai_timeout_seconds: float
    max_response_bytes: int
    max_page_characters: int
    max_output_tokens: int
    max_retries: int
    freshness_hours: int


MODEL = ModelConfig(
    name="deepseek/deepseek-v4.1-flash",
    input_micro_dollars_per_million_tokens=300_000,
    output_micro_dollars_per_million_tokens=1_200_000,
)

CAPS = Caps(
    daily_micro_dollars=100_000,  # $0.10
    monthly_micro_dollars=1_500_000,  # $1.50
)

LIMITS = Limits(
    max_urls_per_run=8,
    fetch_timeout_seconds=10.0,
    ai_timeout_seconds=60.0,
    max_response_bytes=2 * 1024 * 1024,
    max_page_characters=60_000,
    max_output_tokens=4_000,
    max_retries=1,
    freshness_hours=48,
)

MAX_SOURCES_PER_WATCH = 5

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY_ENV = "OPENROUTER_API_KEY"
HISTORY_DAYS = 30
SUSPICIOUS_PERCENT = 60
