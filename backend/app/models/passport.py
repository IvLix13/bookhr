"""Passport tracking."""

from __future__ import annotations

from enum import Enum

from app.extensions import db
from app.models.base import TimestampMixin


class PassportStatus(str, Enum):
    OK = "ok"
    REQUIRES_PREPARATION = "requires_preparation"
    EXPIRED = "expired"


class Passport(db.Model, TimestampMixin):
    __tablename__ = "passports"

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)
    valid_until = db.Column(db.Date, nullable=False)
    series_number = db.Column(db.String(32), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    person = db.relationship("Person", back_populates="passports")
