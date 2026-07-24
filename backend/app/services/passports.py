"""Passport status calculation."""

from __future__ import annotations

from datetime import date

from app.models import PassportStatus
from app.utils.dates import days_until, subtract_months, today_moscow


def compute_passport_status(valid_until: date, reference: date | None = None) -> str:
    ref = reference or today_moscow()
    if valid_until < ref:
        return PassportStatus.EXPIRED.value
    prep_threshold = subtract_months(valid_until, 3)
    if ref >= prep_threshold:
        return PassportStatus.REQUIRES_PREPARATION.value
    return PassportStatus.OK.value


def passport_days_left(valid_until: date, reference: date | None = None) -> int:
    return days_until(valid_until, reference)
