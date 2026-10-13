"""Current attestation: one date, two stable rule events and shared mutations."""

from __future__ import annotations

from datetime import date, timedelta

from app.extensions import db
from app.models import (
    AuditLog,
    Employment,
    EmploymentStatus,
    Event,
    EventStatus,
    EventStatusHistory,
    EventType,
)
from app.services.audit import log_audit
from app.utils.dates import format_long_date_ru, today_moscow

PREPARATION_DAYS = 14
DATE_CLEARED_COMMENT = "Attestation date cleared"
ATTESTATION_TYPES = {
    EventType.ATTESTATION.value,
    EventType.ATTESTATION_PREPARATION.value,
}


def preparation_date(attestation_date: date | None) -> date | None:
    if attestation_date is None:
        return None
    try:
        return attestation_date - timedelta(days=PREPARATION_DAYS)
    except OverflowError as exc:
        raise ValueError(
            "Дата аттестации слишком ранняя для подготовки за 14 дней"
        ) from exc


def attestation_rule_keys(employment: Employment) -> dict[str, str]:
    suffix = f"{employment.company_id}:{employment.id}"
    return {
        EventType.ATTESTATION_PREPARATION.value: f"attestation-preparation:{suffix}",
        EventType.ATTESTATION.value: f"attestation-conduct:{suffix}",
    }


def is_attestation_event(event: Event) -> bool:
    employment = event.employment
    return bool(
        event.event_type in ATTESTATION_TYPES
        and event.source == "rule"
        and employment
        and event.company_id == employment.company_id
        and event.reference_type == "employment"
        and event.reference_id == employment.id
        and event.rule_key == attestation_rule_keys(employment)[event.event_type]
    )


def attestation_mutation_blocked_reason(event: Event) -> str | None:
    if event.event_type not in ATTESTATION_TYPES:
        return None
    if not is_attestation_event(event):
        return "Мероприятие не связано с текущей аттестацией сотрудника"
    if event.employment.status != EmploymentStatus.ACTIVE.value:
        return "Нельзя изменять аттестацию неактивного сотрудника"
    if event.employment.attestation_date is None:
        return "Сначала задайте дату в модуле «Аттестация»"
    return None


def validate_attestation_mutation(event: Event) -> None:
    if event.event_type in ATTESTATION_TYPES and event.employment:
        Employment.query.filter_by(
            id=event.employment_id
        ).with_for_update().populate_existing().one()
        db.session.flush()
        db.session.refresh(event, with_for_update=True)
    reason = attestation_mutation_blocked_reason(event)
    if reason:
        raise ValueError(reason)


def find_attestation_events(employment: Employment) -> dict[str, Event]:
    keys = attestation_rule_keys(employment)
    events = Event.query.filter(
        Event.company_id == employment.company_id,
        Event.employment_id == employment.id,
        Event.source == "rule",
        Event.reference_type == "employment",
        Event.reference_id == employment.id,
        Event.rule_key.in_(list(keys.values())),
        Event.event_type.in_(ATTESTATION_TYPES),
    ).all()
    return {
        event.event_type: event
        for event in events
        if keys[event.event_type] == event.rule_key
    }


def _last_status_change(event: Event) -> EventStatusHistory | None:
    return (
        EventStatusHistory.query.filter_by(event_id=event.id)
        .order_by(
            EventStatusHistory.changed_at.desc(),
            EventStatusHistory.id.desc(),
        )
        .first()
    )


def _was_cleared(event: Event) -> bool:
    last_change = _last_status_change(event)
    if not last_change or last_change.comment != DATE_CLEARED_COMMENT:
        return False
    marker = (
        AuditLog.query.filter_by(
            action="attestation_date_cleared",
            entity_type="event",
            entity_id=event.id,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    # The audit marker identifies the technical transition, even if a user
    # enters the very same text as their cancellation comment.
    return bool(marker and marker.new_value.get("status_history_id") == last_change.id)


def synchronize_attestation_events(employment: Employment) -> int:
    # Serialize rule runs and interactive changes for this employee. Autoflush
    # persists the caller's date before reloading it under the same row lock.
    employment = (
        Employment.query.filter_by(id=employment.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    from app.services.events import OPEN_EDIT_STATUSES, transition_event_status
    from app.services.notifications import (
        queue_notifications_for_event,
        refresh_attestation_notifications,
    )
    from app.services.rule_engine import _upsert_rule_event
    from app.services.employees import get_current_name

    events = find_attestation_events(employment)
    if employment.attestation_date is None or not employment.is_active:
        for event in events.values():
            if event.status in OPEN_EDIT_STATUSES:
                transition_event_status(
                    event, EventStatus.CANCELLED, DATE_CLEARED_COMMENT
                )
                db.session.flush()
                log_audit(
                    "attestation_date_cleared",
                    "event",
                    event.id,
                    None,
                    {"status_history_id": _last_status_change(event).id},
                )
            if event.status in {
                EventStatus.CANCELLED.value,
                EventStatus.COMPLETED.value,
            }:
                refresh_attestation_notifications(event)
        return 0

    prep_date = preparation_date(employment.attestation_date)
    keys = attestation_rule_keys(employment)
    name = get_current_name(employment.person) or "Сотрудник"
    description = f"Дата проведения аттестации: {format_long_date_ru(employment.attestation_date)}"
    specs = (
        (
            EventType.ATTESTATION_PREPARATION,
            prep_date,
            f"Подготовка документов для аттестации: {name}",
        ),
        (
            EventType.ATTESTATION,
            employment.attestation_date,
            f"Проведение аттестации: {name}",
        ),
    )
    for event_type, event_date, title in specs:
        event = events.get(event_type.value)
        created = event is None
        old_date = event.event_date if event else None
        if created:
            event = _upsert_rule_event(
                company_id=employment.company_id,
                employment_id=employment.id,
                rule_key=keys[event_type.value],
                title=title,
                event_type=event_type,
                event_date=event_date,
                description=description,
                reference_type="employment",
                reference_id=employment.id,
            )
        restored = event.status == EventStatus.CANCELLED.value and _was_cleared(event)
        event.title = title
        event.description = description
        event.event_date = event_date
        event.manual_date = False
        if old_date and old_date != event_date:
            log_audit(
                "update",
                "event",
                event.id,
                {"event_date": old_date.isoformat()},
                {"event_date": event_date.isoformat()},
            )
        if restored:
            transition_event_status(
                event, EventStatus.PLANNED, "Attestation date restored"
            )
        if event.status in OPEN_EDIT_STATUSES:
            desired = (
                EventStatus.OVERDUE
                if event_date < today_moscow()
                else EventStatus.PLANNED
            )
            transition_event_status(event, desired, "Attestation date recalculated")
        if (
            created
            or old_date != event_date
            or restored
            or event.status in {"completed", "cancelled"}
        ):
            refresh_attestation_notifications(event)
        else:
            # Reopening may need to recreate unsent deliveries removed on
            # closure. Queueing is idempotent and does not reset retry times.
            queue_notifications_for_event(event)
    return 2


def set_attestation_date(employment: Employment, new_date: date | None) -> None:
    preparation_date(new_date)  # Validate before modifying either source or events.
    employment = (
        Employment.query.filter_by(id=employment.id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    if not employment.is_active:
        raise ValueError("Нельзя изменять аттестацию неактивного сотрудника")
    old_date = employment.attestation_date
    employment.attestation_date = new_date
    if old_date != new_date:
        log_audit(
            "update",
            "employment",
            employment.id,
            {"attestation_date": old_date.isoformat() if old_date else None},
            {"attestation_date": new_date.isoformat() if new_date else None},
        )
    synchronize_attestation_events(employment)


def update_attestation_event_date(event: Event, payload: dict) -> Event:
    validate_attestation_mutation(event)
    if event.event_type != EventType.ATTESTATION.value:
        raise ValueError("Дата подготовки документов рассчитывается автоматически")
    if set(payload) - {"event_date"}:
        raise ValueError("У проведения аттестации можно изменить только дату")
    if event.status == EventStatus.CANCELLED.value:
        raise ValueError("Сначала переоткройте отменённую аттестацию")
    if "event_date" in payload:
        if payload["event_date"] is None:
            raise ValueError("Дату можно очистить только в модуле «Аттестация»")
        set_attestation_date(event.employment, payload["event_date"])
    return event
