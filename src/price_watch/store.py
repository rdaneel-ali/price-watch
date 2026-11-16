"""Storage interface and a local JSON file store for development."""

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from price_watch.models import Check, Listing, Spend, Watch

STORE_PATH_ENV = "PRICE_WATCH_STORE"
DEFAULT_STORE_PATH = Path(".price-watch/store.json")  # gitignored


class StoredCheck(BaseModel):
    """A check and every listing from it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check: Check
    listings: tuple[Listing, ...]


class Store(Protocol):
    def list_watches(self) -> list[Watch]: ...

    def get_watch(self, watch_id: str) -> Watch | None: ...

    def put_watch(self, watch: Watch) -> None: ...

    def save_check(self, check: Check, listings: Sequence[Listing]) -> None: ...

    def list_checks(self, watch_id: str) -> list[StoredCheck]:
        """Oldest first."""
        ...

    def get_spend(self, period: str) -> Spend: ...

    def put_spend(self, spend: Spend) -> None: ...


def resolve_store_path(environ: Mapping[str, str] = os.environ) -> Path:
    value = environ.get(STORE_PATH_ENV)
    return Path(value) if value else DEFAULT_STORE_PATH


class StoreDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watches: dict[str, Watch] = Field(default_factory=dict[str, Watch])
    checks: dict[str, list[StoredCheck]] = Field(default_factory=dict[str, list[StoredCheck]])
    spend: dict[str, Spend] = Field(default_factory=dict[str, Spend])

    @model_validator(mode="after")
    def check_keys_match_ids(self) -> Self:
        for key, watch in self.watches.items():
            if key != watch.watch_id:
                raise ValueError(f"store key {key!r} doesn't match watch_id {watch.watch_id!r}")
        for key, stored_checks in self.checks.items():
            for stored in stored_checks:
                if key != stored.check.watch_id:
                    raise ValueError(
                        f"store key {key!r} doesn't match check watch_id {stored.check.watch_id!r}"
                    )
        for key, spend in self.spend.items():
            if key != spend.period:
                raise ValueError(f"store key {key!r} doesn't match spend period {spend.period!r}")
        return self


class JsonFileStore:
    """One JSON file holding everything. For local development only."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> StoreDocument:
        if not self.path.exists():
            return StoreDocument()
        return StoreDocument.model_validate_json(self.path.read_text())

    def write(self, document: StoreDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(document.model_dump_json(indent=2))
        temporary.replace(self.path)

    def list_watches(self) -> list[Watch]:
        return list(self.read().watches.values())

    def get_watch(self, watch_id: str) -> Watch | None:
        return self.read().watches.get(watch_id)

    def put_watch(self, watch: Watch) -> None:
        document = self.read()
        document.watches[watch.watch_id] = watch
        self.write(document)

    def save_check(self, check: Check, listings: Sequence[Listing]) -> None:
        document = self.read()
        stored = StoredCheck(check=check, listings=tuple(listings))
        document.checks.setdefault(check.watch_id, []).append(stored)
        self.write(document)

    def list_checks(self, watch_id: str) -> list[StoredCheck]:
        return list(self.read().checks.get(watch_id, []))

    def get_spend(self, period: str) -> Spend:
        return self.read().spend.get(period) or Spend(period=period)

    def put_spend(self, spend: Spend) -> None:
        document = self.read()
        document.spend[spend.period] = spend
        self.write(document)
