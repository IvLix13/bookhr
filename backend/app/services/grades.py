"""Grade eligibility helpers."""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import EmployeeGradeHistory, Employment, GradeCatalog
from app.services.employees import get_current_grade, get_current_position
from app.services.grade_catalog import min_years_to_months
from app.utils.dates import today_moscow


def compute_grade_eligibility(
    employment: Employment,
    reference: date | None = None,
) -> dict:
    """Next grade and the date it becomes available.

    A promotion is only possible while the actual grade sits below the grade
    required by the position. The eligible date is when the minimum time in the
    current grade runs out; until the position allows a higher grade there is no
    eligible date at all.
    """
    grade = get_current_grade(employment)
    position = get_current_position(employment)
    position_grade = position.position_grade if position else None
    today = reference or today_moscow()

    next_grade = None
    eligible_date = None
    days_left = None

    if grade and position_grade and grade.grade.rank < position_grade.rank:
        next_grade = GradeCatalog.query.filter(
            GradeCatalog.rank == grade.grade.rank + 1,
            GradeCatalog.is_active.is_(True),
        ).first()
        if next_grade:
            months = min_years_to_months(grade.grade.min_years)
            eligible_date = grade.assigned_date + relativedelta(months=months)
            days_left = (eligible_date - today).days

    return {
        "next_grade": next_grade,
        "eligible_date": eligible_date,
        "days_left": days_left,
        "is_available": eligible_date is not None and eligible_date <= today,
    }


def assign_grade_to_employment(
    employment: Employment,
    grade: GradeCatalog,
    assigned_date: date,
    *,
    basis: str | None = None,
    assigned_by_id: int | None = None,
) -> EmployeeGradeHistory:
    """Close the open grade record and start a new one."""
    current = EmployeeGradeHistory.query.filter_by(
        employment_id=employment.id,
        valid_to=None,
    ).first()
    if current:
        current.valid_to = assigned_date

    history = EmployeeGradeHistory(
        employment_id=employment.id,
        grade_id=grade.id,
        assigned_date=assigned_date,
        assigned_by_id=assigned_by_id,
        basis=basis,
    )
    db.session.add(history)
    db.session.flush()
    return history
