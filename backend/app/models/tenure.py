"""Tenure awards (10/15/20 years)."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class TenureAward(db.Model, TimestampMixin):
    __tablename__ = "tenure_awards"

    id = db.Column(db.Integer, primary_key=True)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=False)
    milestone_years = db.Column(db.Integer, nullable=False)
    milestone_date = db.Column(db.Date, nullable=False)
    is_received = db.Column(db.Boolean, default=False, nullable=False)
    received_date = db.Column(db.Date, nullable=True)

    employment = db.relationship("Employment", back_populates="tenure_awards")

    __table_args__ = (
        db.UniqueConstraint("employment_id", "milestone_years", name="uq_tenure_milestone"),
    )
