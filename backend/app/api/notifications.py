"""Notification settings API."""

from __future__ import annotations

from flask import request

from app.api.helpers import api_response, get_json, load_schema, require_roles
from app.api.schemas import NotificationRuleSchema, NotificationTestSchema
from app.api.serializers import notification_rule_to_dict
from app.extensions import db
from app.models import NotificationRule, RoleName
from app.services.nextcloud import (
    NextcloudError,
    NextcloudNotConfigured,
    search_users,
    send_direct_message,
)
from app.tenant import get_request_company_id


def register_routes(bp):
    @bp.get("/notifications/rules")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def list_rules():
        company_id = get_request_company_id()
        rules = (
            NotificationRule.query.filter(
                db.or_(
                    NotificationRule.company_id.is_(None),
                    NotificationRule.company_id == company_id,
                )
            )
            .order_by(NotificationRule.id.asc())
            .all()
        )
        return api_response([notification_rule_to_dict(r) for r in rules])

    @bp.post("/notifications/rules")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_rule():
        payload = load_schema(NotificationRuleSchema)
        rule = NotificationRule(
            company_id=get_request_company_id(),
            event_type=payload.get("event_type") or None,
            recipient_user_id=payload["recipient_user_id"],
            recipient_display_name=payload.get("recipient_display_name"),
            is_enabled=payload.get("is_enabled", True),
            remind_days_before=payload.get("remind_days_before", 0),
            repeat_interval_days=payload.get("repeat_interval_days", 7),
            overdue_interval_days=payload.get("overdue_interval_days", 3),
            escalation_recipient_user_id=(
                payload.get("escalation_recipient_user_id") or None
            ),
            escalation_recipient_display_name=(
                payload.get("escalation_recipient_display_name") or None
            ),
            escalation_after_days=payload.get("escalation_after_days"),
            send_time_moscow=payload.get("send_time_moscow", "09:00"),
        )
        db.session.add(rule)
        db.session.commit()
        return api_response(notification_rule_to_dict(rule), status=201)

    @bp.patch("/notifications/rules/<int:rule_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_rule(rule_id: int):
        rule = db.session.get(NotificationRule, rule_id)
        if not rule:
            return api_response(message="Not found", status=404)
        if rule.company_id and rule.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)
        payload = get_json()
        effective_recipient = payload.get(
            "recipient_user_id", rule.recipient_user_id
        )
        if payload.get("is_enabled") is True and not effective_recipient:
            return api_response(
                message="Select a Nextcloud recipient before enabling the rule",
                status=400,
            )
        for field in (
            "event_type",
            "recipient_user_id",
            "recipient_display_name",
            "is_enabled",
            "remind_days_before",
            "repeat_interval_days",
            "overdue_interval_days",
            "escalation_recipient_user_id",
            "escalation_recipient_display_name",
            "escalation_after_days",
            "send_time_moscow",
        ):
            if field in payload:
                value = payload[field]
                if field in (
                    "event_type",
                    "escalation_recipient_user_id",
                    "escalation_recipient_display_name",
                ) and value == "":
                    value = None
                setattr(rule, field, value)
        db.session.commit()
        return api_response(notification_rule_to_dict(rule))

    @bp.post("/notifications/test")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def test_notification():
        payload = load_schema(NotificationTestSchema)
        code, body = send_direct_message(
            payload["recipient_user_id"],
            payload.get("message", "Bookuchet test notification"),
        )
        success = 200 <= code < 300
        return api_response(
            {"status_code": code, "response": body},
            status=200 if success else 502,
        )

    @bp.get("/notifications/nextcloud-users")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def nextcloud_users():
        query = request.args.get("q", "").strip()
        if len(query) < 2:
            return api_response(message="Enter at least 2 characters", status=400)
        try:
            users = search_users(query)
        except NextcloudNotConfigured as exc:
            return api_response(message=str(exc), status=503)
        except NextcloudError as exc:
            return api_response(
                message=exc.response_body or str(exc),
                status=502,
            )
        return api_response(
            [
                {"user_id": user.user_id, "display_name": user.display_name}
                for user in users
            ]
        )
