"""Notification settings API."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import api_response, get_json, require_roles
from app.api.serializers import notification_rule_to_dict
from app.extensions import db
from app.models import NotificationRule, RoleName
from app.services.notifications import send_talk_message


def register_routes(bp):
    @bp.get("/notifications/rules")
    @login_required
    def list_rules():
        rules = NotificationRule.query.order_by(NotificationRule.id.asc()).all()
        return api_response([notification_rule_to_dict(r) for r in rules])

    @bp.post("/notifications/rules")
    @require_roles(RoleName.ADMIN)
    def create_rule():
        payload = get_json()
        rule = NotificationRule(
            company_id=payload.get("company_id"),
            event_type=payload.get("event_type") or None,
            room_token=payload["room_token"],
            room_name=payload.get("room_name"),
            is_enabled=payload.get("is_enabled", True),
            remind_days_before=payload.get("remind_days_before", 0),
            repeat_interval_days=payload.get("repeat_interval_days", 7),
            overdue_interval_days=payload.get("overdue_interval_days", 3),
            escalation_room_token=payload.get("escalation_room_token") or None,
            escalation_after_days=payload.get("escalation_after_days"),
            send_time_moscow=payload.get("send_time_moscow", "09:00"),
        )
        db.session.add(rule)
        db.session.commit()
        return api_response(notification_rule_to_dict(rule), status=201)

    @bp.patch("/notifications/rules/<int:rule_id>")
    @require_roles(RoleName.ADMIN)
    def update_rule(rule_id: int):
        rule = db.session.get(NotificationRule, rule_id)
        if not rule:
            return api_response(message="Not found", status=404)
        payload = get_json()
        for field in (
            "company_id",
            "event_type",
            "room_token",
            "room_name",
            "is_enabled",
            "remind_days_before",
            "repeat_interval_days",
            "overdue_interval_days",
            "escalation_room_token",
            "escalation_after_days",
            "send_time_moscow",
        ):
            if field in payload:
                value = payload[field]
                if field in ("event_type", "escalation_room_token") and value == "":
                    value = None
                setattr(rule, field, value)
        db.session.commit()
        return api_response(notification_rule_to_dict(rule))

    @bp.post("/notifications/test")
    @require_roles(RoleName.ADMIN)
    def test_notification():
        payload = get_json()
        code, body = send_talk_message(
            payload["room_token"],
            payload.get("message", "Bookuchet test notification"),
        )
        success = 200 <= code < 300
        return api_response(
            {"status_code": code, "response": body},
            status=200 if success else 502,
        )
