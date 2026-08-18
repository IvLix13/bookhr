"""Rule engine for automatic events."""

from __future__ import annotations

from datetime import date
from typing import Callable

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Contract,
    Employment,
    EmploymentStatus,
    Event,
    EventSource,
    EventStatus,
    EventType,
    Passport,
)
from app.services.employees import get_active_contract, get_current_grade, get_current_name
from app.services.events import (
    record_event_created,
    refresh_overdue_events,
    transition_event_status,
)
from app.services.grades import compute_grade_eligibility
from app.utils.dates import subtract_months


RULE_VERSION = 1
OPEN_EVENT_STATUSES = {EventStatus.PLANNED.value, EventStatus.OVERDUE.value}

CONTRACT_RULE_PREFIX = "contract-renewal-report"
GRADE_PREP_RULE_PREFIX = "grade-preparation"
GRADE_PROMOTION_RULE_PREFIX = "grade-promotion"
# Legacy prefix kept for backward compatibility with existing events.
LEGACY_GRADE_RULE_PREFIX = "grade-review"
PASSPORT_RULE_PREFIX = "passport-preparation"


def contract_rule_key(contract: Contract) -> str:
    return f"{CONTRACT_RULE_PREFIX}:{contract.id}:{contract.end_date.isoformat()}"


def grade_preparation_rule_key(grade_history_id: int, eligible_date: date) -> str:
    return (
        f"{GRADE_PREP_RULE_PREFIX}:{grade_history_id}:{eligible_date.isoformat()}"
    )


def grade_promotion_rule_key(grade_history_id: int, eligible_date: date) -> str:
    return (
        f"{GRADE_PROMOTION_RULE_PREFIX}:{grade_history_id}:{eligible_date.isoformat()}"
    )


def grade_rule_key(grade_history_id: int, eligible_date: date) -> str:
    """Backward-compatible alias for promotion rule keys in tests."""
    return grade_promotion_rule_key(grade_history_id, eligible_date)


def is_grade_preparation_event(event: Event) -> bool:
    return bool(
        event.rule_key
        and event.rule_key.startswith(f"{GRADE_PREP_RULE_PREFIX}:")
    )


def is_grade_promotion_event(event: Event) -> bool:
    if not event.rule_key:
        return event.event_type == EventType.GRADE.value
    return event.rule_key.startswith(
        (f"{GRADE_PROMOTION_RULE_PREFIX}:", f"{LEGACY_GRADE_RULE_PREFIX}:")
    )


def is_passport_preparation_event(event: Event) -> bool:
    if event.event_type != EventType.PASSPORT.value:
        return False
    if event.rule_key and event.rule_key.startswith(f"{PASSPORT_RULE_PREFIX}:"):
        return True
    return event.reference_type == "passport"


def passport_rule_key(passport: Passport) -> str:
    return f"{PASSPORT_RULE_PREFIX}:{passport.id}:{passport.valid_until.isoformat()}"


def _upsert_rule_event(
    company_id: int,
    employment_id: int,
    rule_key: str,
    title: str,
    event_type: EventType,
    event_date: date,
    description: str,
    reference_type: str,
    reference_id: int,
) -> Event | None:
    existing = Event.query.filter_by(rule_key=rule_key).first()
    if existing:
        if existing.status in {EventStatus.COMPLETED.value, EventStatus.CANCELLED.value}:
            return existing
        existing.title = title
        existing.description = description
        existing.event_date = event_date
        existing.employment_id = employment_id
        existing.reference_type = reference_type
        existing.reference_id = reference_id
        return existing

    event = Event(
        company_id=company_id,
        employment_id=employment_id,
        title=title,
        event_type=event_type.value,
        description=description,
        event_date=event_date,
        status=EventStatus.PLANNED.value,
        source=EventSource.RULE.value,
        rule_key=rule_key,
        rule_version=RULE_VERSION,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    try:
        with db.session.begin_nested():
            db.session.add(event)
            db.session.flush()
            record_event_created(event, "Auto-created by rule engine")
    except IntegrityError:
        existing = Event.query.filter_by(rule_key=rule_key).first()
        if existing:
            return existing
        raise

    from app.services.notifications import queue_notifications_for_event

    queue_notifications_for_event(event)
    return event


def find_contract_renewal_event(contract_id: int) -> Event | None:
    """Renewal report of a contract: the open one, otherwise the completed one.

    A completed report still has to be visible on the contracts screen so the
    date it was prepared on does not disappear once the work is done.
    """
    query = Event.query.filter_by(
        reference_type="contract",
        reference_id=contract_id,
        event_type=EventType.REPORT.value,
    ).filter(Event.rule_key.like(f"{CONTRACT_RULE_PREFIX}:%"))

    open_event = (
        query.filter(Event.status.in_(list(OPEN_EVENT_STATUSES)))
        .order_by(Event.event_date.desc())
        .first()
    )
    if open_event:
        return open_event

    return (
        query.filter(Event.status == EventStatus.COMPLETED.value)
        .order_by(Event.event_date.desc())
        .first()
    )


def _active_passport(employment: Employment) -> Passport | None:
    return (
        Passport.query.filter_by(person_id=employment.person_id, is_active=True)
        .order_by(Passport.valid_until.desc())
        .first()
    )


def _expected_rule_keys(employment: Employment) -> set[str]:
    keys: set[str] = set()

    contract = get_active_contract(employment)
    if contract:
        keys.add(contract_rule_key(contract))

    current = get_current_grade(employment)
    if current:
        eligibility = compute_grade_eligibility(employment)
        candidates = eligibility["next_grade_candidates"]
        eligible_date = eligibility["eligible_date"]
        if candidates and eligible_date:
            keys.add(grade_preparation_rule_key(current.id, eligible_date))
            keys.add(grade_promotion_rule_key(current.id, eligible_date))

    passport = _active_passport(employment)
    if passport:
        keys.add(passport_rule_key(passport))

    return keys


def cancel_stale_rule_events(employment: Employment, keep_keys: set[str]) -> int:
    events = (
        Event.query.filter_by(
            employment_id=employment.id,
            source=EventSource.RULE.value,
        )
        .filter(Event.status.in_(list(OPEN_EVENT_STATUSES)))
        .all()
    )
    cancelled = 0
    for event in events:
        if event.rule_key in keep_keys:
            continue
        transition_event_status(
            event,
            EventStatus.CANCELLED,
            "Superseded by recalculation",
        )
        cancelled += 1
    return cancelled


def process_contract_rules(employment: Employment) -> int:
    contract = get_active_contract(employment)
    if not contract:
        return 0

    event_date = subtract_months(contract.end_date, 4)
    name = get_current_name(employment.person) or "Сотрудник"
    _upsert_rule_event(
        company_id=employment.company_id,
        employment_id=employment.id,
        rule_key=contract_rule_key(contract),
        title=f"Подготовить рапорт на продление Договора: {name}",
        event_type=EventType.REPORT,
        event_date=event_date,
        description=f"Договор истекает {contract.end_date.isoformat()}",
        reference_type="contract",
        reference_id=contract.id,
    )
    return 1


def process_grade_rules(employment: Employment) -> int:
    current = get_current_grade(employment)
    if not current:
        return 0

    eligibility = compute_grade_eligibility(employment)
    candidates = eligibility["next_grade_candidates"]
    eligible_date = eligibility["eligible_date"]
    if not candidates or not eligible_date:
        return 0

    prep_date = subtract_months(eligible_date, 1)
    name = get_current_name(employment.person) or "Сотрудник"
    candidate_names = ", ".join(grade.name for grade in candidates)
    description = (
        f"Доступны грейды «{candidate_names}» с {eligible_date.isoformat()}"
    )
    _upsert_rule_event(
        company_id=employment.company_id,
        employment_id=employment.id,
        rule_key=grade_preparation_rule_key(current.id, eligible_date),
        title=f"Подготовить документы на повышение грейда: {name}",
        event_type=EventType.GRADE,
        event_date=prep_date,
        description=description,
        reference_type="employee_grade_history",
        reference_id=current.id,
    )
    _upsert_rule_event(
        company_id=employment.company_id,
        employment_id=employment.id,
        rule_key=grade_promotion_rule_key(current.id, eligible_date),
        title=f"Повышение грейда: {name}",
        event_type=EventType.GRADE,
        event_date=eligible_date,
        description=description,
        reference_type="employee_grade_history",
        reference_id=current.id,
    )
    return 2


def process_passport_rules(employment: Employment) -> int:
    passport = _active_passport(employment)
    if not passport:
        return 0

    prep_date = subtract_months(passport.valid_until, 3)
    name = get_current_name(employment.person) or "Сотрудник"
    _upsert_rule_event(
        company_id=employment.company_id,
        employment_id=employment.id,
        rule_key=passport_rule_key(passport),
        title=f"Подготовка документов для паспорта: {name}",
        event_type=EventType.PASSPORT,
        event_date=prep_date,
        description=f"Паспорт действителен до {passport.valid_until.isoformat()}",
        reference_type="passport",
        reference_id=passport.id,
    )
    return 1


# Registry of rule processors keyed by stats field name.
RULE_PROCESSORS: list[tuple[str, Callable[[Employment], int]]] = [
    ("contracts", process_contract_rules),
    ("grades", process_grade_rules),
    ("passports", process_passport_rules),
]


def recalculate_employment_events(employment: Employment) -> dict[str, int]:
    """Create/update current rule events and cancel superseded open ones."""
    if employment.status != EmploymentStatus.ACTIVE.value:
        cancelled = cancel_stale_rule_events(employment, set())
        return {"contracts": 0, "grades": 0, "passports": 0, "cancelled": cancelled}

    stats = {name: processor(employment) for name, processor in RULE_PROCESSORS}
    stats["cancelled"] = cancel_stale_rule_events(
        employment,
        _expected_rule_keys(employment),
    )
    return stats


def run_rule_engine(company_id: int | None = None) -> dict[str, int]:
    query = Employment.query.filter_by(status=EmploymentStatus.ACTIVE.value)
    if company_id:
        query = query.filter_by(company_id=company_id)

    stats = {"contracts": 0, "grades": 0, "passports": 0, "cancelled": 0}
    for employment in query.all():
        result = recalculate_employment_events(employment)
        for key, value in result.items():
            stats[key] = stats.get(key, 0) + value

    refresh_overdue_events(company_id)
    return stats
