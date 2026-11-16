"""One chat completion call through httpx. No SDK, no tools."""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from price_watch.config import LIMITS, MICRO_DOLLARS_PER_DOLLAR, OPENROUTER_URL


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cost_micro_dollars: int | None  # None when OpenRouter reported no cost


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    usage: Usage


class OpenRouterError(Exception):
    """The call failed. `usage` is set only if OpenRouter reported it."""

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class ReportedUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float | None = None  # credits, which are US dollars


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str | None = None


class Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: Message


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: list[Choice] = []
    usage: ReportedUsage = ReportedUsage()


def dollars_to_micro(dollars: float) -> int | None:
    """Round up, so a reported cost is never understated. Negative or odd values give None."""
    if dollars < 0 or dollars != dollars:  # negative or NaN
        return None
    micro = Decimal(str(dollars)) * MICRO_DOLLARS_PER_DOLLAR
    return int(micro.to_integral_value(rounding=ROUND_CEILING))


def make_ai_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(timeout=LIMITS.ai_timeout_seconds, transport=transport)


def parse_chat_response(payload: object) -> ChatResult:
    try:
        response = ChatResponse.model_validate(payload)
    except ValidationError as error:
        raise OpenRouterError("unexpected response shape") from error
    reported = response.usage
    cost = dollars_to_micro(reported.cost) if reported.cost is not None else None
    usage = Usage(reported.prompt_tokens, reported.completion_tokens, cost)
    content = response.choices[0].message.content if response.choices else None
    return ChatResult(content or "", usage)


def call_chat(client: httpx.Client, api_key: str, body: dict[str, Any]) -> ChatResult:
    try:
        response = client.post(
            OPENROUTER_URL, json=body, headers={"Authorization": f"Bearer {api_key}"}
        )
    except httpx.HTTPError as error:
        raise OpenRouterError(f"request failed: {type(error).__name__}") from error
    if response.status_code != 200:
        raise OpenRouterError(f"status {response.status_code}")
    try:
        payload: object = response.json()
    except ValueError as error:
        raise OpenRouterError("response was not JSON") from error
    return parse_chat_response(payload)
