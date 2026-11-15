"""Storage interface and a local JSON file store for development."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from price_watch.models import Watch


class StoreDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watches: dict[str, Watch] = {}


STORE_PATH_ENV = "PRICE_WATCH_STORE"
DEFAULT_STORE_PATH = Path(".price-watch/store.json")  # gitignored


class Store(Protocol):
    def list_watches(self) -> list[Watch]: ...

    def get_watch(self, watch_id: str) -> Watch | None: ...

    def put_watch(self, watch: Watch) -> None: ...


def resolve_store_path(environ: Mapping[str, str] = os.environ) -> Path:
    value = environ.get(STORE_PATH_ENV)
    return Path(value) if value else DEFAULT_STORE_PATH


class JsonFileStore:
    """One JSON file: {"watches": {watch_id: watch}}. For local development only."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read_watches(self) -> dict[str, Watch]:
        if not self.path.exists():
            return {}
        document = StoreDocument.model_validate_json(self.path.read_text())
        return document.watches

    def write_watches(self, watches: dict[str, Watch]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = StoreDocument(watches=watches)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(document.model_dump_json(indent=2))
        temporary.replace(self.path)

    def list_watches(self) -> list[Watch]:
        return list(self.read_watches().values())

    def get_watch(self, watch_id: str) -> Watch | None:
        return self.read_watches().get(watch_id)

    def put_watch(self, watch: Watch) -> None:
        watches = self.read_watches()
        watches[watch.watch_id] = watch
        self.write_watches(watches)
