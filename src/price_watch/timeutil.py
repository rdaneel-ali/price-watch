"""UTC timestamps. `now` is always passed in, so only the edges read the clock."""

from datetime import UTC, datetime


def format_utc(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(text)


def day_period(moment: datetime) -> str:
    return "DAY#" + moment.astimezone(UTC).strftime("%Y-%m-%d")


def month_period(moment: datetime) -> str:
    return "MONTH#" + moment.astimezone(UTC).strftime("%Y-%m")
