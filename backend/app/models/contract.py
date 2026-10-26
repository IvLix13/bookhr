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


class ContractRenewal(db.Model, TimestampMixin):
    __tablename__ = "contract_renewals"
    id = db.Column(db.Integer, primary_key=True)
    source_contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False, unique=True)
    report_event_id = db.Column(db.Integer, db.ForeignKey("events.id"), unique=True)
    signing_event_id = db.Column(db.Integer, db.ForeignKey("events.id"), unique=True)
    result_contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), unique=True)
    source_end_date = db.Column(db.Date, nullable=False)
    term_years = db.Column(db.Float)
    activated_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (db.CheckConstraint("term_years IS NULL OR term_years > 0", name="ck_renewal_term_positive"),)
