"""Grade catalog and employee grade history."""

from __future__ import annotations

from sqlalchemy import event, select

from app.extensions import db
from app.models.base import TimestampMixin


class GradeCatalog(db.Model, TimestampMixin):
    __tablename__ = "grade_catalog"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    min_years = db.Column(db.Numeric(5, 2), default=1, nullable=False)
    extra_year_without_university = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    grade_history = db.relationship("EmployeeGradeHistory", back_populates="grade")


class EmployeeGradeHistory(db.Model, TimestampMixin):
    __tablename__ = "employee_grade_history"

    id = db.Column(db.Integer, primary_key=True)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grade_catalog.id"), nullable=False)
    assigned_date = db.Column(db.Date, nullable=False)
    rank_at_assignment = db.Column(db.Integer, nullable=False)
    rank_started_at = db.Column(db.Date, nullable=False)
    required_months = db.Column(db.Integer, nullable=False)
    education_status_at_rank_entry = db.Column(db.String(16), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    basis = db.Column(db.Text, nullable=True)
    valid_to = db.Column(db.Date, nullable=True)

    employment = db.relationship("Employment", back_populates="grade_history")
    grade = db.relationship("GradeCatalog", back_populates="grade_history")
    assigned_by = db.relationship("User")


@event.listens_for(EmployeeGradeHistory, "before_insert")
def populate_grade_tenure_snapshot(mapper, connection, target) -> None:
    """Protect history invariants for trusted bulk and legacy callers."""
    if (
        target.rank_at_assignment is not None
        and target.rank_started_at is not None
        and target.required_months is not None
        and target.education_status_at_rank_entry is not None
    ):
        return

    grade_row = connection.execute(
        select(
            GradeCatalog.rank,
            GradeCatalog.min_years,
            GradeCatalog.extra_year_without_university,
        ).where(GradeCatalog.id == target.grade_id)
    ).one()
    employment_table = db.metadata.tables["employments"]
    person_table = db.metadata.tables["persons"]
    education_status = connection.execute(
        select(person_table.c.education_status)
        .select_from(
            employment_table.join(
                person_table,
                employment_table.c.person_id == person_table.c.id,
            )
        )
        .where(employment_table.c.id == target.employment_id)
    ).scalar_one()

    target.rank_at_assignment = grade_row.rank
    target.rank_started_at = target.assigned_date
    target.required_months = int(round(float(grade_row.min_years) * 12))
    if education_status == "no" and grade_row.extra_year_without_university:
        target.required_months += 12
    target.education_status_at_rank_entry = education_status
