"""Event service."""

from __future__ import annotations

from datetime import date

from flask_login import current_user

from app.extensions import db
from app.models import Event, EventStatus, EventStatusHistory, EventType
from app.services.audit import _current_user_id, log_audit
from app.utils.dates import today_moscow


def transition_event_status(
    event: Event,
    new_status: EventStatus,
    comment: str | None = None,
) -> Event:
    old_status = event.status
    event.status = new_status.value

    if new_status == EventStatus.COMPLETED:
        event.completed_at = db.func.now()
        if _current_user_id():
            event.completed_by_id = _current_user_id()
        event.completion_comment = comment

    history = EventStatusHistory(
        event_id=event.id,
        old_status=old_status,
        new_status=new_status.value,
        changed_by_id=_current_user_id(),
        comment=comment,
    )
    db.session.add(history)
    log_audit(
        "event_status_change",
        "event",
        event.id,
        {"status": old_status},
        {"status": new_status.value, "comment": comment},
    )
    return event


def create_manual_event(
    company_id: int,
    title: str,
    event_type: EventType,
    event_date: date,
    description: str | None = None,
    employment_id: int | None = None,
) -> Event:
    event = Event(
        company_id=company_id,
        employment_id=employment_id,
        title=title,
        event_type=event_type.value,
        description=description,
        event_date=event_date,
        created_by_id=_current_user_id(),
    )
    db.session.add(event)
    db.session.flush()
    transition_event_status(event, EventStatus.PLANNED, "Created")
    log_audit("create", "event", event.id, None, {"title": title})
    return event


def refresh_overdue_events(company_id: int | None = None) -> int:
    today = today_moscow()
    query = Event.query.filter(
        Event.status == EventStatus.PLANNED.value,
        Event.event_date < today,
    )
    if company_id:
        query = query.filter(Event.company_id == company_id)

    count = 0
    for event in query.all():
        transition_event_status(event, EventStatus.OVERDUE, "Auto-marked overdue")
        count += 1
    return count
