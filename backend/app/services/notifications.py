"""Nextcloud Talk notification service."""

from __future__ import annotations

from datetime import datetime, timedelta

import requests
from flask import current_app

from app.extensions import db
from app.models import (
    DeliveryStatus,
    Event,
    EventStatus,
    NotificationDelivery,
    NotificationRule,
)
from app.models.base import utcnow
from app.utils.dates import MOSCOW


def _build_message(event: Event) -> str:
    employee_name = ""
    if event.employment and event.employment.person:
        from app.services.employees import get_current_name

        employee_name = get_current_name(event.employment.person) or ""
    parts = [f"**{event.title}**", f"Дата: {event.event_date.isoformat()}"]
    if employee_name:
        parts.append(f"Сотрудник: {employee_name}")
    if event.description:
        parts.append(event.description)
    return "\n".join(parts)


def send_talk_message(room_token: str, message: str) -> tuple[int, str]:
    base_url = current_app.config.get("NEXTCLOUD_BASE_URL", "").rstrip("/")
    token = current_app.config.get("NEXTCLOUD_BOT_TOKEN", "")
    if not base_url or not token:
        return 0, "Nextcloud not configured"

    url = f"{base_url}/ocs/v2.php/apps/spreed/api/v1/bot/{room_token}/message"
    headers = {
        "OCS-APIRequest": "true",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            url,
            json={"message": message},
            headers=headers,
            timeout=15,
        )
        return response.status_code, response.text[:500]
    except requests.RequestException as exc:
        return 0, str(exc)[:500]


def queue_notifications_for_event(event: Event) -> int:
    rules = NotificationRule.query.filter(
        NotificationRule.is_enabled.is_(True),
        db.or_(
            NotificationRule.company_id.is_(None),
            NotificationRule.company_id == event.company_id,
        ),
        db.or_(
            NotificationRule.event_type.is_(None),
            NotificationRule.event_type == event.event_type,
        ),
    ).all()

    created = 0
    for rule in rules:
        key = f"notify:{event.id}:{rule.id}:{event.event_date.isoformat()}"
        existing = NotificationDelivery.query.filter_by(idempotency_key=key).first()
        if existing:
            continue

        delivery = NotificationDelivery(
            event_id=event.id,
            rule_id=rule.id,
            idempotency_key=key,
            recipient=rule.room_token,
            status=DeliveryStatus.PENDING.value,
            next_attempt_at=utcnow(),
        )
        db.session.add(delivery)
        created += 1
    return created


def process_pending_notifications() -> dict[str, int]:
    now = utcnow()
    moscow_now = datetime.now(MOSCOW)
    current_time = moscow_now.strftime("%H:%M")

    pending = NotificationDelivery.query.filter(
        NotificationDelivery.status.in_(
            [DeliveryStatus.PENDING.value, DeliveryStatus.FAILED.value]
        ),
        db.or_(
            NotificationDelivery.next_attempt_at.is_(None),
            NotificationDelivery.next_attempt_at <= now,
        ),
    ).all()

    stats = {"sent": 0, "failed": 0, "skipped": 0}
    for delivery in pending:
        event = delivery.event
        rule = delivery.rule
        if not event or event.status == EventStatus.COMPLETED.value:
            stats["skipped"] += 1
            continue

        if rule and rule.send_time_moscow > current_time:
            stats["skipped"] += 1
            continue

        delivery.attempt_count += 1
        code, body = send_talk_message(delivery.recipient, _build_message(event))
        delivery.response_code = code
        delivery.response_body = body

        if 200 <= code < 300:
            delivery.status = DeliveryStatus.SENT.value
            delivery.sent_at = utcnow()
            stats["sent"] += 1
        else:
            delivery.status = DeliveryStatus.FAILED.value
            interval = rule.overdue_interval_days if rule else 3
            if event.status == EventStatus.OVERDUE.value and rule:
                interval = rule.overdue_interval_days
            elif rule:
                interval = rule.repeat_interval_days
            delivery.next_attempt_at = utcnow() + timedelta(days=interval)
            stats["failed"] += 1

    db.session.commit()
    return stats
