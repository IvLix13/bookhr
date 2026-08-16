"""Grade eligibility helpers."""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from app.extensions import db
from app.models import (
    EducationStatus,
    EmployeeGradeHistory,
    Employment,
    GradeCatalog,
    PositionHistory,
)
from app.services.grade_catalog import min_years_to_months
from app.utils.dates import today_moscow


def _current_grade(employment: Employment) -> EmployeeGradeHistory | None:
    return (
        EmployeeGradeHistory.query.filter_by(employment_id=employment.id, valid_to=None)
        .order_by(EmployeeGradeHistory.assigned_date.desc())
        .first()
    )


def _current_position(employment: Employment) -> PositionHistory | None:
    return (
        PositionHistory.query.filter_by(employment_id=employment.id, valid_to=None)
        .order_by(PositionHistory.valid_from.desc())
        .first()
    )


def _new_rank_snapshot(
    employment: Employment,
    grade: GradeCatalog,
    assigned_date: date,
) -> dict:
    education_status = employment.person.education_status
    if education_status not in {EducationStatus.YES.value, EducationStatus.NO.value}:
        raise ValueError("Укажите наличие высшего образования у сотрудника")

    required_months = min_years_to_months(grade.min_years)
    if (
        education_status == EducationStatus.NO.value
        and grade.extra_year_without_university
    ):
        required_months += 12

    return {
        "rank_at_assignment": grade.rank,
        "rank_started_at": assigned_date,
        "required_months": required_months,
        "education_status_at_rank_entry": education_status,
    }


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
    grade = _current_grade(employment)
    position = _current_position(employment)
    position_grade = position.position_grade if position else None
    today = reference or today_moscow()

    next_grade = None
    next_rank = None
    next_grade_candidates = []
    eligible_date = None
    days_left = None
    blocked_reason = None

    if grade and position_grade and grade.grade.rank < position_grade.rank:
        next_rank = (
            db.session.query(func.min(GradeCatalog.rank))
            .filter(
                GradeCatalog.rank > grade.grade.rank,
                GradeCatalog.rank <= position_grade.rank,
                GradeCatalog.is_active.is_(True),
            )
            .scalar()
        )
        if next_rank is not None:
            next_grade_candidates = (
                GradeCatalog.query.filter(
                    GradeCatalog.rank == next_rank,
                    GradeCatalog.is_active.is_(True),
                )
                .order_by(GradeCatalog.name.asc(), GradeCatalog.id.asc())
                .all()
            )
        if len(next_grade_candidates) == 1:
            next_grade = next_grade_candidates[0]

        education_status = grade.education_status_at_rank_entry
        if education_status not in {
            EducationStatus.YES.value,
            EducationStatus.NO.value,
        }:
            blocked_reason = "Укажите наличие высшего образования у сотрудника"
        elif next_grade_candidates:
            months = grade.required_months
            eligible_date = grade.rank_started_at + relativedelta(months=months)
            days_left = (eligible_date - today).days

    return {
        "next_rank": next_rank,
        "next_grade_candidates": next_grade_candidates,
        "next_grade": next_grade,
        "requires_grade_choice": len(next_grade_candidates) > 1,
        "blocked_reason": blocked_reason,
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
    current = _current_grade(employment)
    if current:
        current.valid_to = assigned_date

    if current and current.rank_at_assignment == grade.rank:
        snapshot = {
            "rank_at_assignment": current.rank_at_assignment,
            "rank_started_at": current.rank_started_at,
            "required_months": current.required_months,
            "education_status_at_rank_entry": current.education_status_at_rank_entry,
        }
    else:
        snapshot = _new_rank_snapshot(employment, grade, assigned_date)

    history = EmployeeGradeHistory(
        employment_id=employment.id,
        grade_id=grade.id,
        assigned_date=assigned_date,
        assigned_by_id=assigned_by_id,
        basis=basis,
        **snapshot,
    )
    db.session.add(history)
    db.session.flush()
    return history
