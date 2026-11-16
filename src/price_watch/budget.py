"""Spend caps. Reserve the worst case before every attempt, then settle with the real cost."""

from dataclasses import dataclass
from datetime import datetime

from price_watch.config import CAPS, Caps
from price_watch.models import Spend
from price_watch.openrouter import Usage
from price_watch.store import Store
from price_watch.timeutil import day_period, month_period


class BudgetExceededError(Exception):
    """Reserving the worst case would pass a daily or monthly cap."""


@dataclass(frozen=True, slots=True)
class Reservation:
    micro_dollars: int


class SpendLedger:
    def __init__(self, store: Store, now: datetime, caps: Caps = CAPS) -> None:
        self.store = store
        self.caps = caps
        self.day = day_period(now)
        self.month = month_period(now)

    def current(self) -> tuple[Spend, Spend]:
        return self.store.get_spend(self.day), self.store.get_spend(self.month)

    def reserve(self, worst_case_micro_dollars: int) -> Reservation:
        if worst_case_micro_dollars < 0:
            raise ValueError("a reservation must not be negative")
        day, month = self.current()
        if (
            day.cost + worst_case_micro_dollars > self.caps.daily_micro_dollars
            or month.cost + worst_case_micro_dollars > self.caps.monthly_micro_dollars
        ):
            raise BudgetExceededError("a spend cap would be passed")
        for spend in (day, month):
            self.store.put_spend(
                spend.model_copy(update={"cost": spend.cost + worst_case_micro_dollars})
            )
        return Reservation(worst_case_micro_dollars)

    def settle(self, reservation: Reservation, usage: Usage | None) -> None:
        """Replace the reservation with the reported cost. With no reported cost, the
        reservation stays. Every settled attempt counts as one call."""
        reported = usage.cost_micro_dollars if usage else None
        adjustment = 0 if reported is None else reported - reservation.micro_dollars
        for spend in self.current():
            self.store.put_spend(
                spend.model_copy(
                    update={
                        "cost": spend.cost + adjustment,
                        "calls": spend.calls + 1,
                        "input_tokens": spend.input_tokens + (usage.input_tokens if usage else 0),
                        "output_tokens": spend.output_tokens
                        + (usage.output_tokens if usage else 0),
                    }
                )
            )
