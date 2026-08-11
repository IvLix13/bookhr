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
from app.services.employees import get_current_name
from app.services.events import effective_event_status
from app.utils.dates import MOSCOW, today_moscow


def _days_overdue(event: Event) -> int:
    today = today_moscow()
    if event.event_date >= today:
        return 0
    return (today - event.event_date).days


def _build_message(event: Event, *, escalated: bool = False) -> str:
    employee_name = ""
    if event.employment and event.employment.person:
        employee_name = get_current_name(event.employment.person) or ""

    days = _days_overdue(event)
    if escalated and days > 0:
        parts = [f"⚠️ ПРОСРОЧЕНО {days} дн.: **{event.title}**"]
    elif days > 0 and effective_event_status(event) == EventStatus.OVERDUE.value:
        parts = [f"**{event.title}** (просрочено {days} дн.)"]
    else:
        parts = [f"**{event.title}**"]

    parts.append(f"Дата: {event.event_date.isoformat()}")
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


def _queue_delivery(
    *,
    event_id: int,
    rule_id: int,
    idempotency_key: str,
    recipient: str,
) -> bool:
    existing = NotificationDelivery.query.filter_by(
        idempotency_key=idempotency_key
    ).first()
    if existing:
        return False

    delivery = NotificationDelivery(
        event_id=event_id,
        rule_id=rule_id,
        idempotency_key=idempotency_key,
        recipient=recipient,
        status=DeliveryStatus.PENDING.value,
        next_attempt_at=utcnow(),
    )
    db.session.add(delivery)
    return True


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
        if _queue_delivery(
            event_id=event.id,
            rule_id=rule.id,
            idempotency_key=key,
            recipient=rule.room_token,
        ):
            created += 1

        created += queue_escalation_for_event(event, rule)
    return created


def queue_escalation_for_event(event: Event, rule: NotificationRule) -> int:
    """Queue escalation delivery when overdue threshold is reached."""
    if not rule.escalation_room_token or rule.escalation_after_days is None:
        return 0

    if effective_event_status(event) != EventStatus.OVERDUE.value:
        return 0

    days = _days_overdue(event)
    if days < rule.escalation_after_days:
        return 0

    bucket = days // max(rule.escalation_after_days, 1)
    key = f"escalate:{event.id}:{rule.id}:{bucket}"
    if _queue_delivery(
        event_id=event.id,
        rule_id=rule.id,
        idempotency_key=key,
        recipient=rule.escalation_room_token,
    ):
        return 1
    return 0


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

    stats = {"sent": 0, "failed": 0, "skipped": 0, "escalations_queued": 0}
    for delivery in pending:
        event = delivery.event
        rule = delivery.rule
        if not event or event.status == EventStatus.COMPLETED.value:
            stats["skipped"] += 1
            continue

        if rule and rule.send_time_moscow > current_time:
            stats["skipped"] += 1
            continue

        escalated = bool(
            delivery.idempotency_key
            and delivery.idempotency_key.startswith("escalate:")
        )

        delivery.attempt_count += 1
        code, body = send_talk_message(
            delivery.recipient,
            _build_message(event, escalated=escalated),
        )
        delivery.response_code = code
        delivery.response_body = body

        if 200 <= code < 300:
            delivery.status = DeliveryStatus.SENT.value
            delivery.sent_at = utcnow()
            stats["sent"] += 1
        else:
            delivery.status = DeliveryStatus.FAILED.value
            interval = 3
            if rule:
                if effective_event_status(event) == EventStatus.OVERDUE.value:
                    interval = rule.overdue_interval_days
                else:
                    interval = rule.repeat_interval_days
            delivery.next_attempt_at = utcnow() + timedelta(days=interval)
            stats["failed"] += 1

        # Opportunistically queue escalation while processing overdue events.
        if rule and not escalated:
            stats["escalations_queued"] += queue_escalation_for_event(event, rule)

    db.session.commit()
    return stats
