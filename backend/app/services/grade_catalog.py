"""Grade catalog validation helpers."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import GradeCatalog


def validate_min_years(value) -> Decimal:
    years = Decimal(str(value))
    if years <= 0:
        raise ValueError("min_years must be positive")
    doubled = years * 2
    if doubled != doubled.to_integral_value():
        raise ValueError("min_years must use 0.5 year steps")
    return years


def min_years_to_months(min_years) -> int:
    return int(round(float(min_years) * 12))


def validate_rank(rank: int) -> int:
    rank = int(rank)
    if rank < 1:
        raise ValueError("rank must be at least 1")
    return rank


def validate_rank_continuity(*, rank: int, exclude_id: int | None = None) -> None:
    """Ensure ranks 1..rank-1 exist so promotion chains stay intact."""
    if rank <= 1:
        return
    query = GradeCatalog.query.filter(GradeCatalog.rank < rank)
    if exclude_id is not None:
        query = query.filter(GradeCatalog.id != exclude_id)
    existing = {item.rank for item in query.all()}
    missing = [value for value in range(1, rank) if value not in existing]
    if missing:
        raise ValueError(f"missing prerequisite ranks: {', '.join(map(str, missing))}")


def apply_grade_catalog_payload(grade: GradeCatalog, payload: dict) -> None:
    if "name" in payload:
        name = str(payload["name"]).strip()
        if not name:
            raise ValueError("name is required")
        grade.name = name

    next_rank = grade.rank
    if "rank" in payload:
        next_rank = validate_rank(payload["rank"])
        validate_rank_continuity(rank=next_rank, exclude_id=grade.id)
        grade.rank = next_rank

    if "min_years" in payload:
        grade.min_years = validate_min_years(payload["min_years"])

    if "is_active" in payload:
        grade.is_active = bool(payload["is_active"])


def commit_grade_catalog() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("grade name or rank must be unique") from exc
