"""Events and status history."""

from __future__ import annotations

from enum import Enum

from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class EventType(str, Enum):
    CONTRACT = "contract"
    GRADE = "grade"
    AWARD = "award"
    REPORT = "report"
    PASSPORT = "passport"
    MANUAL = "manual"


class EventSource(str, Enum):
    MANUAL = "manual"
    RULE = "rule"
    IMPORT = "import"


class EventStatus(str, Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class Event(db.Model, TimestampMixin):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=True)
    title = db.Column(db.String(256), nullable=False)
    event_type = db.Column(db.String(32), nullable=False)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.Date, nullable=False)
    manual_date = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(32), default=EventStatus.PLANNED.value, nullable=False)
    source = db.Column(db.String(32), default=EventSource.MANUAL.value, nullable=False)
    rule_key = db.Column(db.String(256), nullable=True)
    rule_version = db.Column(db.Integer, default=1, nullable=False)
    reference_type = db.Column(db.String(64), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    completed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completion_comment = db.Column(db.Text, nullable=True)

    company = db.relationship("Company")
    employment = db.relationship("Employment", back_populates="events")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    completed_by = db.relationship("User", foreign_keys=[completed_by_id])
    status_history = db.relationship("EventStatusHistory", back_populates="event")

    __table_args__ = (
        db.UniqueConstraint("rule_key", name="uq_event_rule_key"),
    )


class EventStatusHistory(db.Model):
    __tablename__ = "event_status_history"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    old_status = db.Column(db.String(32), nullable=True)
    new_status = db.Column(db.String(32), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    event = db.relationship("Event", back_populates="status_history")
    changed_by = db.relationship("User")
