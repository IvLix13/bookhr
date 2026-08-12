"""Grade catalog and employee grade history."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class GradeCatalog(db.Model, TimestampMixin):
    __tablename__ = "grade_catalog"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    rank = db.Column(db.Integer, unique=True, nullable=False)
    min_years = db.Column(db.Numeric(5, 2), default=1, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    grade_history = db.relationship("EmployeeGradeHistory", back_populates="grade")


class EmployeeGradeHistory(db.Model, TimestampMixin):
    __tablename__ = "employee_grade_history"

    id = db.Column(db.Integer, primary_key=True)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grade_catalog.id"), nullable=False)
    assigned_date = db.Column(db.Date, nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    basis = db.Column(db.Text, nullable=True)
    valid_to = db.Column(db.Date, nullable=True)

    employment = db.relationship("Employment", back_populates="grade_history")
    grade = db.relationship("GradeCatalog", back_populates="grade_history")
    assigned_by = db.relationship("User")
