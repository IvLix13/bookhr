import pytest
from datetime import date

from dateutil.relativedelta import relativedelta

from app.utils.dates import (
    add_months,
    add_years,
    calculate_contract_end,
    calculate_term_years,
    subtract_months,
    today_moscow,
)
from app.services.passports import compute_passport_status
from app.models import PassportStatus


def test_subtract_months_calendar():
    assert subtract_months(date(2026, 11, 30), 3) == date(2026, 8, 30)
    assert subtract_months(date(2026, 5, 31), 1) == date(2026, 4, 30)


def test_add_months_calendar():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_passport_status_thresholds():
    expiry = date(2026, 12, 1)
    assert compute_passport_status(expiry, date(2026, 5, 1)) == PassportStatus.OK.value
    assert (
        compute_passport_status(expiry, subtract_months(expiry, 4))
        == PassportStatus.REQUIRES_PREPARATION.value
    )
    assert compute_passport_status(expiry, date(2026, 12, 2)) == PassportStatus.EXPIRED.value


def test_calculate_passport_renewal_date():
    from app.services.passports import calculate_passport_renewal_date

    assert calculate_passport_renewal_date(date(2026, 9, 1)) == date(2031, 9, 1)


def test_grade_eligibility_date():
    assigned = date(2024, 1, 15)
    eligible = assigned + relativedelta(months=18)
    reminder = subtract_months(eligible, 1)
    assert reminder == date(2025, 6, 15)


def test_calculate_contract_end():
    start = date(2024, 9, 1)
    assert calculate_contract_end(start, 1) == date(2025, 9, 1)
    assert calculate_contract_end(start, 2) == date(2026, 9, 1)
    assert calculate_contract_end(start, 3.5) == date(2028, 3, 1)


def test_calculate_term_years():
    start = date(2024, 9, 1)
    assert calculate_term_years(start, date(2025, 9, 1)) == 1.0
    assert calculate_term_years(start, date(2026, 9, 1)) == 2.0
    assert calculate_term_years(start, date(2026, 3, 1)) == 1.5
    assert calculate_term_years(start, date(2027, 9, 1)) == 3.0
    assert calculate_term_years(start, date(2029, 9, 1)) == 5.0

    with pytest.raises(ValueError, match="позже даты начала"):
        calculate_term_years(start, start)

    with pytest.raises(ValueError, match="позже даты начала"):
        calculate_term_years(start, date(2024, 8, 1))


