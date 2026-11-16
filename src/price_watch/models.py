"""Stored records and the contract responses other apps rely on.

Money is integer cents, AI spend is integer micro-dollars, timestamps are UTC ISO 8601 with
a trailing Z.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from price_watch.config import MAX_SOURCES_PER_WATCH

MANUAL_SOURCE_ID = "manual"
MANUAL_SOURCE_NAME = "Manual"


def check_https_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("must be an absolute https:// URL")
    return value


def check_not_manual_name(value: str) -> str:
    if value.strip().casefold() == MANUAL_SOURCE_NAME.casefold():
        raise ValueError(f"'{MANUAL_SOURCE_NAME}' is reserved for the manual price")
    return value


def check_real_timestamp(value: str) -> str:
    datetime.fromisoformat(value)  # raises ValueError on a date or time that doesn't exist
    return value


HttpsUrl = Annotated[str, AfterValidator(check_https_url)]
Cents = Annotated[int, Field(gt=0, strict=True)]
MicroDollars = Annotated[int, Field(ge=0, strict=True)]
Count = Annotated[int, Field(ge=0, strict=True)]
UtcTimestamp = Annotated[
    str,
    StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"),
    AfterValidator(check_real_timestamp),
]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Condition(StrEnum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ListingStatus(StrEnum):
    FOUND = "found"
    CONFIRMED = "confirmed"


class SourceStatus(StrEnum):
    OK = "ok"
    FETCH_FAILED = "fetch_failed"
    TOO_LARGE = "too_large"
    NO_LISTINGS = "no_listings"
    AI_FAILED = "ai_failed"
    BUDGET_STOPPED = "budget_stopped"
    SKIPPED = "skipped"


class Source(Model):
    source_id: str = Field(min_length=1)
    name: Annotated[str, Field(min_length=1), AfterValidator(check_not_manual_name)]
    url: HttpsUrl
    enabled: bool = True
    terms_note: str | None = None


class ManualPrice(Model):
    price: Cents
    url: HttpsUrl | None = None
    note: str | None = None
    set_at: UtcTimestamp


class Watch(Model):
    watch_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    spec: str = Field(min_length=1)
    target_price: Cents
    sources: tuple[Source, ...] = Field(default=(), max_length=MAX_SOURCES_PER_WATCH)
    manual_price: ManualPrice | None = None
    enabled: bool = True
    created_at: UtcTimestamp
    updated_at: UtcTimestamp

    @model_validator(mode="after")
    def check_unique_source_ids(self) -> Self:
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)) or MANUAL_SOURCE_ID in ids:
            raise ValueError("source_id must be unique in the watch and not 'manual'")
        return self


class Listing(Model):
    """One item found for one watch."""

    title: str
    price: Cents
    condition: Condition
    url: HttpsUrl | None = None
    source_id: str
    meets_spec: bool
    spec_reason: str
    ai_confidence: Confidence | None = None
    meets_target: bool
    suspicious: bool
    suspicious_reason: str | None = None
    status: ListingStatus
    seen_at: UtcTimestamp

    @model_validator(mode="after")
    def check_manual_rules(self) -> Self:
        if self.source_id == MANUAL_SOURCE_ID:
            if self.ai_confidence is not None or self.suspicious:
                raise ValueError("a manual listing has no confidence and is never suspicious")
        elif self.url is None or self.ai_confidence is None:
            raise ValueError("an AI listing needs a url and ai_confidence")
        return self


class SourceResult(Model):
    source_id: str
    status: SourceStatus
    listing_count: Count = 0


class Check(Model):
    """One per watch per run. Its best listing, kept for every check, is the price history."""

    watch_id: str
    user_id: str = Field(min_length=1)
    checked_at: UtcTimestamp
    sources: tuple[SourceResult, ...]
    best: Listing | None = None


class ApiKey(Model):
    key_id: str
    user_id: str
    name: str
    secret_hash: str
    revoked: bool = False
    created_at: UtcTimestamp
    last_used_at: UtcTimestamp | None = None


class Spend(Model):
    period: Annotated[
        str, StringConstraints(pattern=r"^(DAY#\d{4}-\d{2}-\d{2}|MONTH#\d{4}-\d{2})$")
    ]
    cost: MicroDollars = 0
    calls: Count = 0
    input_tokens: Count = 0
    output_tokens: Count = 0


# Contract responses (what other apps read over HTTP).


class WatchListItem(Model):
    watch_id: str
    name: str
    target_price: Cents


class ContractListing(Model):
    title: str
    price: Cents
    condition: Condition
    url: HttpsUrl | None
    source_name: str
    meets_target: bool
    suspicious: bool
    suspicious_reason: str | None
    status: ListingStatus
    seen_at: UtcTimestamp

    @model_validator(mode="after")
    def check_url_only_null_for_manual(self) -> Self:
        if self.url is None and self.source_name != MANUAL_SOURCE_NAME:
            raise ValueError("url is null only for the listing whose source_name is 'Manual'")
        return self


class ContractListingDetail(ContractListing):
    meets_spec: bool
    spec_reason: str


class BestResponse(Model):
    watch_id: str
    name: str
    target_price: Cents
    checked_at: UtcTimestamp | None
    check_ok: bool
    best: ContractListing | None


class ListingsResponse(Model):
    watch_id: str
    checked_at: UtcTimestamp | None
    listings: tuple[ContractListingDetail, ...]
