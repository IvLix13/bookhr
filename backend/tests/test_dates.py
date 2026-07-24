from datetime import date

from dateutil.relativedelta import relativedelta

from app.utils.dates import add_months, subtract_months, today_moscow
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
        compute_passport_status(expiry, subtract_months(expiry, 3))
        == PassportStatus.REQUIRES_PREPARATION.value
    )
    assert compute_passport_status(expiry, date(2026, 12, 2)) == PassportStatus.EXPIRED.value


def test_grade_eligibility_date():
    assigned = date(2024, 1, 15)
    eligible = assigned + relativedelta(months=12)
    reminder = subtract_months(eligible, 1)
    assert reminder == date(2024, 12, 15)
