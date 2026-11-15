"""Validate the AI's answer against the listing shape."""

import json
import logging
from collections.abc import Collection

from pydantic import BaseModel, ConfigDict, ValidationError

from price_watch.models import Condition, Confidence, HttpsUrl, check_https_url

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """The answer did not match the shape. Worth one retry."""


class WatchJudgment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    watch_id: str
    meets_spec: bool
    spec_reason: str


class ExtractedListing(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    title: str
    price_cents: int
    condition: Condition
    url: HttpsUrl
    ai_confidence: Confidence
    judgments: tuple[WatchJudgment, ...]


def has_usable_price_and_url(item: dict[str, object]) -> bool:
    price = item.get("price_cents")
    url = item.get("url")
    if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
        return False
    if not isinstance(url, str):
        return False
    try:
        check_https_url(url)
    except ValueError:
        return False
    return True


def parse_extraction(content: str, watch_ids: Collection[str]) -> list[ExtractedListing]:
    """Listings without a price above 0 or an https url are dropped and logged, never guessed.
    Any other mismatch with the shape raises ExtractionError."""
    try:
        data: object = json.loads(content)
    except ValueError as error:
        raise ExtractionError("answer is not JSON") from error
    if not isinstance(data, dict) or not isinstance(data.get("listings"), list):  # pyright: ignore[reportUnknownMemberType]
        raise ExtractionError("answer has no listings list")
    expected = set(watch_ids)
    listings: list[ExtractedListing] = []
    for item in data["listings"]:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, dict):
            raise ExtractionError("a listing is not an object")
        raw: dict[str, object] = item  # pyright: ignore[reportUnknownVariableType]
        if not has_usable_price_and_url(raw):
            logger.warning("dropped a listing without a price above 0 or an https url")
            continue
        try:
            listing = ExtractedListing.model_validate(raw)
        except ValidationError as error:
            raise ExtractionError("a listing does not match the shape") from error
        judged = [judgment.watch_id for judgment in listing.judgments]
        if len(judged) != len(expected) or set(judged) != expected:
            raise ExtractionError("judgments do not cover each watch exactly once")
        listings.append(listing)
    return listings
