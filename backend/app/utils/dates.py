"""Date and timezone utilities."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

MOSCOW = ZoneInfo("Europe/Moscow")


def today_moscow() -> date:
    return datetime.now(MOSCOW).date()


def add_months(value: date, months: int) -> date:
    return value + relativedelta(months=months)


def subtract_months(value: date, months: int) -> date:
    return value - relativedelta(months=months)


def days_until(target: date, reference: date | None = None) -> int:
    ref = reference or today_moscow()
    return (target - ref).days


def normalize_full_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()
