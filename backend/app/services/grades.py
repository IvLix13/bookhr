"""Grade eligibility helpers."""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

from app.models import Employment, GradeCatalog
from app.services.employees import get_current_grade
from app.utils.dates import today_moscow


def compute_grade_eligibility(
    employment: Employment,
    reference: date | None = None,
) -> dict:
    grade = get_current_grade(employment)
    today = reference or today_moscow()
    next_grade = None
    eligible_date = None
    days_left = None

    if grade:
        next_grade_obj = GradeCatalog.query.filter(
            GradeCatalog.rank == grade.grade.rank + 1,
            GradeCatalog.is_active.is_(True),
        ).first()
        if next_grade_obj:
            next_grade = next_grade_obj
            eligible_date = grade.assigned_date + relativedelta(months=grade.grade.min_months)
            days_left = (eligible_date - today).days

    return {
        "next_grade": next_grade,
        "eligible_date": eligible_date,
        "days_left": days_left,
    }
