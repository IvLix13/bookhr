"""Tenure awards (10/15/20 years)."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class TenureAward(db.Model, TimestampMixin):
    __tablename__ = "tenure_awards"

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    milestone_years = db.Column(db.Integer, nullable=False)
    milestone_date = db.Column(db.Date, nullable=False)
    is_received = db.Column(db.Boolean, default=False, nullable=False)
    received_date = db.Column(db.Date, nullable=True)

    person = db.relationship("Person", back_populates="tenure_awards")
    company = db.relationship("Company")

    __table_args__ = (
        db.UniqueConstraint(
            "person_id",
            "company_id",
            "milestone_years",
            name="uq_tenure_person_milestone",
        ),
    )
