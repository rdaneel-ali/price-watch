from datetime import UTC, datetime

import pytest

from price_watch.budget import BudgetExceededError, SpendLedger
from price_watch.config import Caps
from price_watch.models import Spend
from price_watch.openrouter import Usage


class MemoryStore:
    def __init__(self) -> None:
        self.spend: dict[str, Spend] = {}

    def get_spend(self, period: str) -> Spend:
        return self.spend.get(period) or Spend(period=period)

    def put_spend(self, spend: Spend) -> None:
        self.spend[spend.period] = spend


NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
CAPS = Caps(daily_micro_dollars=1000, monthly_micro_dollars=5000)


def make_ledger(store: MemoryStore) -> SpendLedger:
    return SpendLedger(store, NOW, CAPS)  # pyright: ignore[reportArgumentType]


def test_reserve_adds_to_day_and_month() -> None:
    store = MemoryStore()
    make_ledger(store).reserve(400)
    assert store.spend["DAY#2026-11-14"].cost == 400
    assert store.spend["MONTH#2026-11"].cost == 400


def test_reserve_refuses_when_day_cap_would_pass() -> None:
    store = MemoryStore()
    ledger = make_ledger(store)
    ledger.reserve(600)
    with pytest.raises(BudgetExceededError):
        ledger.reserve(401)
    assert store.spend["DAY#2026-11-14"].cost == 600  # a refused reservation changes nothing


def test_reserve_refuses_when_month_cap_would_pass() -> None:
    store = MemoryStore()
    store.put_spend(Spend(period="MONTH#2026-11", cost=4800))
    with pytest.raises(BudgetExceededError):
        make_ledger(store).reserve(300)


def test_reserve_up_to_the_cap_is_allowed() -> None:
    make_ledger(MemoryStore()).reserve(1000)


def test_settle_replaces_reservation_with_reported_cost() -> None:
    store = MemoryStore()
    ledger = make_ledger(store)
    reservation = ledger.reserve(400)
    ledger.settle(reservation, Usage(100, 20, 150))
    day = store.spend["DAY#2026-11-14"]
    assert (day.cost, day.calls, day.input_tokens, day.output_tokens) == (150, 1, 100, 20)


def test_settle_without_reported_cost_keeps_reservation() -> None:
    store = MemoryStore()
    ledger = make_ledger(store)
    reservation = ledger.reserve(400)
    ledger.settle(reservation, None)
    ledger.settle(ledger.reserve(100), Usage(5, 5, None))
    day = store.spend["DAY#2026-11-14"]
    assert day.cost == 500 and day.calls == 2
