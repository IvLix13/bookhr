"""Employee rewards (non-tenure)."""

from __future__ import annotations

from enum import Enum

from app.extensions import db
from app.models.base import TimestampMixin


class RewardStatus(str, Enum):
    NOT_DELIVERED = "not_delivered"
    IN_HR = "in_hr"
    DELIVERED = "delivered"


class Reward(db.Model, TimestampMixin):
    __tablename__ = "rewards"

    id = db.Column(db.Integer, primary_key=True)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=False)
    reward_type = db.Column(db.String(256), nullable=False)
    status = db.Column(
        db.String(32),
        default=RewardStatus.NOT_DELIVERED.value,
        nullable=False,
    )
    directive_text = db.Column(db.Text, nullable=True)
    delivered_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    employment = db.relationship("Employment", back_populates="rewards")
