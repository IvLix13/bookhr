"""Explicit maintenance operations. Callers own commit/rollback; previews only read."""
from datetime import timedelta

from sqlalchemy import or_, select, text

from app.extensions import db
from app.models import AuditLog, Contract, ContractRenewal, Employment, Event, EventStatus, EventStatusHistory, NotificationDelivery
from app.services.audit import log_audit
from app.services.events import transition_event_status
from app.services.notifications import queue_notifications_for_event
from app.services.rule_engine import OPEN_EVENT_STATUSES, contract_expiry_rule_key, process_contract_rules
from app.utils.dates import today_moscow


EXTENSION_ACTION = "maintenance_contracts_plus_one_day"


def _lock_maintenance():
    # Serialize the two maintenance commands, including an empty database.
    if db.session.get_bind().dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 69198241})
    # Keep the application's employee -> contract/event lock order.
    db.session.execute(select(Employment.id).order_by(Employment.id).with_for_update()).all()


def extend_contracts_one_day(*, apply=False):
    """Add exactly one day to EVERY end_date, keeping start dates and terms."""
    if apply:
        _lock_maintenance()
    already_applied = AuditLog.query.filter_by(action=EXTENSION_ACTION, entity_type="database").first() is not None
    if apply and already_applied:
        raise ValueError("Добавление дня уже выполнено в этой базе. Повторное увеличение запрещено.")
    query = Contract.query.order_by(Contract.id)
    contracts = query.with_for_update().all() if apply else query.all()
    by_id = {contract.id: contract for contract in contracts}
    renewals = ContractRenewal.query.order_by(ContractRenewal.id).all()
    mismatched_starts = sum(
        1 for renewal in renewals
        if renewal.result_contract_id in by_id and renewal.source_contract_id in by_id
        and by_id[renewal.result_contract_id].start_date != by_id[renewal.source_contract_id].end_date + timedelta(days=2)
    )
    result = {
        "applied": False, "already_applied": already_applied, "contracts": len(contracts),
        "linked_periods_start_mismatch_after": mismatched_starts,
        "sample": [{"id": contract.id, "old_end": contract.end_date.isoformat(),
                    "new_end": (contract.end_date + timedelta(days=1)).isoformat()}
                   for contract in contracts[:10]],
    }
    if already_applied:
        result["sample"] = []
    if not apply or not contracts:
        return result
    for contract in contracts:
        old_end = contract.end_date
        contract.end_date += timedelta(days=1)
        log_audit("contract_end_plus_one_day", "contract", contract.id,
                  {"end_date": old_end.isoformat()}, {"end_date": contract.end_date.isoformat()})
    for renewal in renewals:
        if renewal.source_contract_id in by_id:
            renewal.source_end_date = by_id[renewal.source_contract_id].end_date
    db.session.flush()

    # Only contract rules are recalculated; other domain modules are untouched.
    contract_events = Event.query.filter(
        Event.reference_type == "contract", Event.source == "rule",
        Event.status.in_(OPEN_EVENT_STATUSES),
    ).all()
    for event in contract_events:
        contract = by_id.get(event.reference_id)
        if (contract and event.event_type == "contract" and event.rule_key
                and event.rule_key.startswith("contract-expiry:")
                and event.rule_key != contract_expiry_rule_key(contract)):
            transition_event_status(event, EventStatus.CANCELLED, "Superseded by recalculation")
            queue_notifications_for_event(event)
    employment_ids = {contract.employment_id for contract in contracts}
    for employment in Employment.query.filter(Employment.id.in_(employment_ids)).order_by(Employment.id):
        if employment.status == "active":
            process_contract_rules(employment)
    for event in Event.query.filter(
        Event.reference_type == "contract", Event.source == "rule",
        Event.status == "planned", Event.event_date < today_moscow(),
    ).all():
        if event.reference_id in by_id:
            transition_event_status(event, EventStatus.OVERDUE, "Auto-marked overdue")
    result["applied"] = True
    log_audit(EXTENSION_ACTION, "database", None, None,
              {"contracts": len(contracts), "days": 1, "start_dates_changed": False,
               "linked_periods_start_mismatch_after": mismatched_starts})
    return result


def purge_cancelled_events(*, apply=False):
    """Delete cancelled events with their deliveries/history and detach renewal FKs."""
    if apply:
        _lock_maintenance()
    query = Event.query.filter_by(status="cancelled").order_by(Event.id)
    events = query.with_for_update().all() if apply else query.all()
    ids = [event.id for event in events]
    renewals = ContractRenewal.query.filter(or_(
        ContractRenewal.report_event_id.in_(ids), ContractRenewal.signing_event_id.in_(ids),
    )).all() if ids else []
    result = {
        "applied": False, "events": len(ids),
        "status_history": EventStatusHistory.query.filter(EventStatusHistory.event_id.in_(ids)).count(),
        "notification_deliveries": NotificationDelivery.query.filter(NotificationDelivery.event_id.in_(ids)).count(),
        "contract_stage_links": sum(int(row.report_event_id in ids) + int(row.signing_event_id in ids) for row in renewals),
    }
    if not apply or not ids:
        return result
    id_set = set(ids)
    for renewal in renewals:
        if renewal.report_event_id in id_set:
            renewal.report_event_id = None
        if renewal.signing_event_id in id_set:
            renewal.signing_event_id = None
    db.session.flush()
    NotificationDelivery.query.filter(NotificationDelivery.event_id.in_(ids)).delete(synchronize_session="fetch")
    EventStatusHistory.query.filter(EventStatusHistory.event_id.in_(ids)).delete(synchronize_session="fetch")
    Event.query.filter(Event.id.in_(ids)).delete(synchronize_session="fetch")
    result["applied"] = True
    log_audit("purge_cancelled_events", "database", None, None,
              {key: value for key, value in result.items() if key != "applied"})
    return result
