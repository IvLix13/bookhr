"""Manual statistics uploaded from Excel."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin


class ManualStatisticsSnapshot(db.Model, TimestampMixin):
    __tablename__ = "manual_statistics_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("companies.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    items = db.Column(db.JSON, nullable=False, default=list)
    source_filename = db.Column(db.String(255), nullable=True)

    company = db.relationship("Company")
