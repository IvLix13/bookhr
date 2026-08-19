"""Date and timezone utilities."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

MOSCOW = ZoneInfo("Europe/Moscow")

_RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

_RU_LONG_DATE_RE = re.compile(
    r"^(\d{1,2})\s+([а-яё]+)\s+(\d{4})$",
    re.IGNORECASE,
)


def today_moscow() -> date:
    return datetime.now(MOSCOW).date()


def add_months(value: date, months: int) -> date:
    return value + relativedelta(months=months)


def subtract_months(value: date, months: int) -> date:
    return value - relativedelta(months=months)


def add_years(value: date, years: float | int) -> date:
    whole_years = int(years)
    remaining_months = round((years - whole_years) * 12)
    return value + relativedelta(years=whole_years, months=remaining_months)


def calculate_contract_end(start_date: date, term_years: float | int) -> date:
    return add_years(start_date, term_years)


def subtract_years(value: date, years: float | int) -> date:
    whole_years = int(years)
    remaining_months = round((years - whole_years) * 12)
    return value - relativedelta(years=whole_years, months=remaining_months)


def calculate_contract_start(end_date: date, term_years: float | int) -> date:
    if term_years <= 0:
        raise ValueError("Срок договора должен быть больше нуля")
    start_date = subtract_years(end_date, term_years)
    if start_date >= end_date:
        raise ValueError("Дата окончания договора должна быть позже даты начала")
    return start_date


def calculate_term_years(start_date: date, end_date: date) -> float:
    if end_date <= start_date:
        raise ValueError("Дата окончания договора должна быть позже даты начала")
    delta = relativedelta(end_date, start_date)
    approx_months = delta.years * 12 + delta.months + (delta.days / 30.4375)
    years = approx_months / 12.0
    rounded = round(years, 1)
    if abs(rounded - round(rounded)) < 0.05:
        return float(round(rounded))
    return float(rounded)


def days_until(target: date, reference: date | None = None) -> int:
    ref = reference or today_moscow()
    return (target - ref).days


def normalize_full_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


def format_display_date_ru(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def parse_flexible_date(value: Any) -> date | None:
    """Parse dates from Excel cells and Russian text formats.

    Supported:
    - datetime / date objects
    - ``ДД.ММ.ГГГГ``
    - ``ГГГГ-ММ-ДД`` (optional time suffix)
    - ``14 ноября 2026 г.`` / ``14 ноября 2026``
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = re.sub(r"\s+", " ", str(value).strip())
    if not text:
        return None

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    ru_text = re.sub(r"\s*г\.?\s*$", "", text, flags=re.IGNORECASE).strip().lower()
    match = _RU_LONG_DATE_RE.match(ru_text)
    if match:
        day_s, month_name, year_s = match.groups()
        month = _RU_MONTHS.get(month_name)
        if month is None:
            return None
        try:
            return date(int(year_s), month, int(day_s))
        except ValueError:
            return None

    return None
