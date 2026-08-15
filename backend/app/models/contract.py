"""Employment contracts."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class Contract(db.Model, TimestampMixin):
    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    term_years = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    employment = db.relationship("Employment", back_populates="contracts")
