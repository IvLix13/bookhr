"""Passport status calculation."""

from __future__ import annotations

from datetime import date

from app.models import PassportStatus
from app.utils.dates import add_years, days_until, subtract_months, today_moscow

PASSPORT_VALIDITY_YEARS = 5
PASSPORT_PREP_MONTHS = 4


def calculate_passport_renewal_date(current_valid_until: date) -> date:
    """Next passport expires five years after the current one."""
    return add_years(current_valid_until, PASSPORT_VALIDITY_YEARS)


def compute_passport_status(valid_until: date, reference: date | None = None) -> str:
    ref = reference or today_moscow()
    if valid_until < ref:
        return PassportStatus.EXPIRED.value
    prep_threshold = subtract_months(valid_until, PASSPORT_PREP_MONTHS)
    if ref >= prep_threshold:
        return PassportStatus.REQUIRES_PREPARATION.value
    return PassportStatus.OK.value


def passport_days_left(valid_until: date, reference: date | None = None) -> int:
    return days_until(valid_until, reference)
