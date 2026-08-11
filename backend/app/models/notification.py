"""Nextcloud notification rules and delivery log."""

from __future__ import annotations

from enum import Enum

from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationRule(db.Model, TimestampMixin):
    __tablename__ = "notification_rules"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    event_type = db.Column(db.String(32), nullable=True)
    room_token = db.Column(db.String(128), nullable=False)
    room_name = db.Column(db.String(256), nullable=True)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    remind_days_before = db.Column(db.Integer, default=0, nullable=False)
    repeat_interval_days = db.Column(db.Integer, default=7, nullable=False)
    overdue_interval_days = db.Column(db.Integer, default=3, nullable=False)
    escalation_room_token = db.Column(db.String(128), nullable=True)
    escalation_after_days = db.Column(db.Integer, nullable=True)
    send_time_moscow = db.Column(db.String(5), default="09:00", nullable=False)

    company = db.relationship("Company")


class NotificationDelivery(db.Model):
    __tablename__ = "notification_deliveries"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    rule_id = db.Column(db.Integer, db.ForeignKey("notification_rules.id"), nullable=True)
    idempotency_key = db.Column(db.String(256), unique=True, nullable=False)
    recipient = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(32), default=DeliveryStatus.PENDING.value, nullable=False)
    response_code = db.Column(db.Integer, nullable=True)
    response_body = db.Column(db.Text, nullable=True)
    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    next_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    event = db.relationship("Event")
    rule = db.relationship("NotificationRule")
