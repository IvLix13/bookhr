"""Grade catalog validation helpers."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import EmployeeGradeHistory, GradeCatalog, PositionHistory


def validate_min_years(value) -> Decimal:
    years = Decimal(str(value))
    if years <= 0:
        raise ValueError("min_years must be positive")
    scaled = years * 10
    if scaled != scaled.to_integral_value():
        raise ValueError("min_years must use 0.1 year steps")
    return years


def min_years_to_months(min_years) -> int:
    return int(round(float(min_years) * 12))


def validate_rank(rank: int) -> int:
    rank = int(rank)
    if rank < 1:
        raise ValueError("rank must be at least 1")
    return rank


def validate_extra_year_without_university(value) -> bool:
    if not isinstance(value, bool):
        raise ValueError("extra_year_without_university must be boolean")
    return value


def apply_grade_catalog_payload(grade: GradeCatalog, payload: dict) -> None:
    if "name" in payload:
        name = str(payload["name"]).strip()
        if not name:
            raise ValueError("name is required")
        grade.name = name

    next_rank = grade.rank
    if "rank" in payload:
        next_rank = validate_rank(payload["rank"])
        grade.rank = next_rank

    if "min_years" in payload:
        grade.min_years = validate_min_years(payload["min_years"])

    if "is_active" in payload:
        grade.is_active = bool(payload["is_active"])

    if "extra_year_without_university" in payload:
        grade.extra_year_without_university = validate_extra_year_without_university(
            payload["extra_year_without_university"]
        )


def commit_grade_catalog() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("grade name must be unique") from exc


def grade_usage_employment_ids(grade_id: int) -> set[int]:
    """Employments currently using this grade as actual or position grade."""
    actual_ids = {
        row[0]
        for row in db.session.query(EmployeeGradeHistory.employment_id)
        .filter(
            EmployeeGradeHistory.grade_id == grade_id,
            EmployeeGradeHistory.valid_to.is_(None),
        )
        .all()
    }
    position_ids = {
        row[0]
        for row in db.session.query(PositionHistory.employment_id)
        .filter(
            PositionHistory.position_grade_id == grade_id,
            PositionHistory.valid_to.is_(None),
        )
        .all()
    }
    return actual_ids | position_ids


def delete_grade_catalog(grade: GradeCatalog) -> None:
    """Unassign the grade from employees, then remove it from the catalog.

    Current actual-grade history is removed so the employee field becomes empty
    («—»). Historical rows for this grade are removed so the FK can be dropped.
    Position grades pointing at this catalog entry are cleared.
    """
    EmployeeGradeHistory.query.filter_by(grade_id=grade.id).delete(synchronize_session=False)
    PositionHistory.query.filter_by(position_grade_id=grade.id).update(
        {PositionHistory.position_grade_id: None},
        synchronize_session=False,
    )
    db.session.delete(grade)
    commit_grade_catalog()
