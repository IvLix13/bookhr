"""Event service."""

from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import (
    Employment,
    Event,
    EventSource,
    EventStatus,
    EventStatusHistory,
    EventType,
)
from app.services.audit import _current_user_id, log_audit
from app.utils.dates import today_moscow


class InvalidEventTransition(Exception):
    """Raised when an event status transition is not allowed."""

    def __init__(self, old_status: str, new_status: str) -> None:
        self.old_status = old_status
        self.new_status = new_status
        super().__init__(
            f"Invalid event transition: {old_status} → {new_status}"
        )


ALLOWED_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.PLANNED: {
        EventStatus.OVERDUE,
        EventStatus.COMPLETED,
        EventStatus.CANCELLED,
    },
    EventStatus.OVERDUE: {
        EventStatus.PLANNED,
        EventStatus.COMPLETED,
        EventStatus.CANCELLED,
    },
    EventStatus.COMPLETED: {
        EventStatus.PLANNED,
    },
    EventStatus.CANCELLED: {
        EventStatus.PLANNED,
    },
}


def effective_event_status(
    event: Event,
    reference: date | None = None,
) -> str:
    """Return display status, treating past planned events as overdue."""
    today = reference or today_moscow()
    if (
        event.status == EventStatus.PLANNED.value
        and event.event_date < today
    ):
        return EventStatus.OVERDUE.value
    return event.status


def apply_status_filter(query, status: str | None, reference: date | None = None):
    """Filter events by effective status (virtual overdue on read)."""
    if not status:
        return query

    today = reference or today_moscow()
    if status == EventStatus.OVERDUE.value:
        return query.filter(
            db.or_(
                Event.status == EventStatus.OVERDUE.value,
                db.and_(
                    Event.status == EventStatus.PLANNED.value,
                    Event.event_date < today,
                ),
            )
        )
    if status == EventStatus.PLANNED.value:
        return query.filter(
            Event.status == EventStatus.PLANNED.value,
            Event.event_date >= today,
        )
    return query.filter(Event.status == status)


def effectively_overdue_filter(reference: date | None = None):
    """SQLAlchemy filter for materialised or virtual overdue events."""
    today = reference or today_moscow()
    return db.or_(
        Event.status == EventStatus.OVERDUE.value,
        db.and_(
            Event.status == EventStatus.PLANNED.value,
            Event.event_date < today,
        ),
    )


def transition_event_status(
    event: Event,
    new_status: EventStatus,
    comment: str | None = None,
    *,
    force: bool = False,
) -> Event:
    old_status = event.status
    if old_status == new_status.value:
        return event

    if not force:
        try:
            current = EventStatus(old_status)
        except ValueError as exc:
            raise InvalidEventTransition(old_status, new_status.value) from exc
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise InvalidEventTransition(old_status, new_status.value)

    event.status = new_status.value

    if new_status == EventStatus.COMPLETED:
        event.completed_at = db.func.now()
        if _current_user_id():
            event.completed_by_id = _current_user_id()
        event.completion_comment = comment
    elif new_status in {EventStatus.PLANNED, EventStatus.CANCELLED}:
        event.completed_at = None
        event.completed_by_id = None
        event.completion_comment = None

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


def record_event_created(event: Event, comment: str) -> None:
    """Write initial status history for a newly created planned event."""
    history = EventStatusHistory(
        event_id=event.id,
        old_status=None,
        new_status=EventStatus.PLANNED.value,
        changed_by_id=_current_user_id(),
        comment=comment,
    )
    db.session.add(history)


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
        status=EventStatus.PLANNED.value,
        created_by_id=_current_user_id(),
    )
    db.session.add(event)
    db.session.flush()
    record_event_created(event, "Created")
    log_audit("create", "event", event.id, None, {"title": title})

    from app.services.notifications import queue_notifications_for_event

    queue_notifications_for_event(event)
    return event


OPEN_EDIT_STATUSES = {
    EventStatus.PLANNED.value,
    EventStatus.OVERDUE.value,
}


class EventMutationError(Exception):
    """Raised when an event cannot be updated or deleted."""


def refresh_events_after_mutation(
    *,
    company_id: int,
    employment: Employment | None = None,
) -> None:
    """Recalculate rule events and refresh overdue flags after a mutation."""
    from app.services.rule_engine import recalculate_employment_events

    if employment:
        recalculate_employment_events(employment)
    refresh_overdue_events(company_id)


def update_manual_event(event: Event, payload: dict) -> Event:
    if event.source != EventSource.MANUAL.value:
        raise EventMutationError("Only manually created events can be edited")
    if event.status not in OPEN_EDIT_STATUSES:
        raise EventMutationError("Only open events can be edited")
    if not payload:
        return event

    old_values = {
        "title": event.title,
        "event_type": event.event_type,
        "event_date": event.event_date.isoformat(),
        "description": event.description,
        "employment_id": event.employment_id,
    }

    if "title" in payload:
        event.title = payload["title"]
    if "event_type" in payload:
        event.event_type = payload["event_type"].value
    if "event_date" in payload:
        event.event_date = payload["event_date"]
    if "description" in payload:
        event.description = payload["description"]
    if "employment_id" in payload:
        employment_id = payload["employment_id"]
        if employment_id is not None:
            employment = db.session.get(Employment, employment_id)
            if not employment or employment.company_id != event.company_id:
                raise EventMutationError("Employment not found")
        event.employment_id = employment_id

    new_values = {
        "title": event.title,
        "event_type": event.event_type,
        "event_date": event.event_date.isoformat(),
        "description": event.description,
        "employment_id": event.employment_id,
    }
    log_audit("update", "event", event.id, old_values, new_values)
    return event


def delete_manual_event(event: Event) -> Employment | None:
    if event.source != EventSource.MANUAL.value:
        raise EventMutationError("Only manually created events can be deleted")

    employment = event.employment
    event_id = event.id
    log_audit("delete", "event", event_id, {"title": event.title}, None)
    EventStatusHistory.query.filter_by(event_id=event_id).delete(
        synchronize_session=False
    )
    db.session.delete(event)
    return employment


def refresh_overdue_events(company_id: int | None = None) -> int:
    """Materialize overdue status (background / mutating paths only)."""
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
