import json
from pathlib import Path

import pytest

from price_watch.models import Watch
from price_watch.store import DEFAULT_STORE_PATH, STORE_PATH_ENV, JsonFileStore, resolve_store_path

NOW = "2026-11-14T14:00:00Z"


def make_watch(watch_id: str = "w1") -> Watch:
    return Watch(
        watch_id=watch_id,
        user_id="u",
        name="n",
        spec="s",
        target_price=100,
        created_at=NOW,
        updated_at=NOW,
    )


def test_missing_file_is_empty(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "s.json")
    assert store.list_watches() == []
    assert store.get_watch("w1") is None


def test_put_then_get_and_list(tmp_path: Path) -> None:
    store = JsonFileStore(tmp_path / "nested" / "s.json")
    store.put_watch(make_watch("w1"))
    store.put_watch(make_watch("w2"))
    assert store.get_watch("w1") == make_watch("w1")
    assert [w.watch_id for w in store.list_watches()] == ["w1", "w2"]


def test_bad_format_raises(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text("[1]")
    with pytest.raises(ValueError):
        JsonFileStore(path).list_watches()


def test_path_from_env_with_default() -> None:
    assert resolve_store_path({STORE_PATH_ENV: "/x/y.json"}) == Path("/x/y.json")
    assert resolve_store_path({}) == DEFAULT_STORE_PATH


def test_watch_key_must_match_watch_id(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"watches": {"alias": make_watch("w1").model_dump(mode="json")}}))
    with pytest.raises(ValueError, match="doesn't match"):
        JsonFileStore(path).get_watch("alias")
