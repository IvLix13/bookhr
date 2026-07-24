"""Rule engine for automatic events."""

from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    EmploymentStatus,
    Event,
    EventSource,
    EventStatus,
    EventType,
    GradeCatalog,
    Passport,
)
from app.services.employees import get_active_contract, get_current_grade, get_current_name
from app.services.events import transition_event_status
from app.utils.dates import subtract_months, today_moscow


RULE_VERSION = 1


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
        return existing

    event = Event(
        company_id=company_id,
        employment_id=employment_id,
        title=title,
        event_type=event_type.value,
        description=description,
        event_date=event_date,
        source=EventSource.RULE.value,
        rule_key=rule_key,
        rule_version=RULE_VERSION,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.session.add(event)
    db.session.flush()
    transition_event_status(event, EventStatus.PLANNED, "Auto-created by rule engine")
    return event


def process_contract_rules(employment: Employment) -> int:
    contract = get_active_contract(employment)
    if not contract:
        return 0

    event_date = subtract_months(contract.end_date, 4)
    rule_key = f"contract-renewal-report:{contract.id}:{contract.end_date.isoformat()}"
    name = get_current_name(employment.person) or "Сотрудник"
    _upsert_rule_event(
        company_id=employment.company_id,
        employment_id=employment.id,
        rule_key=rule_key,
        title=f"Подготовить рапорт на продление договора: {name}",
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

    next_grade = (
        GradeCatalog.query.filter(
            GradeCatalog.rank == current.grade.rank + 1,
            GradeCatalog.is_active.is_(True),
        ).first()
    )
    if not next_grade:
        return 0

    from dateutil.relativedelta import relativedelta

    eligible_date = current.assigned_date + relativedelta(months=current.grade.min_months)
    event_date = subtract_months(eligible_date, 1)

    rule_key = (
        f"grade-review:{current.id}:{eligible_date.isoformat()}"
    )
    name = get_current_name(employment.person) or "Сотрудник"
    _upsert_rule_event(
        company_id=employment.company_id,
        employment_id=employment.id,
        rule_key=rule_key,
        title=f"Рассмотреть повышение грейда: {name}",
        event_type=EventType.GRADE,
        event_date=event_date,
        description=(
            f"Доступен грейд «{next_grade.name}» с {eligible_date.isoformat()}"
        ),
        reference_type="employee_grade_history",
        reference_id=current.id,
    )
    return 1


def process_passport_rules(employment: Employment) -> int:
    passport = (
        Passport.query.filter_by(person_id=employment.person_id, is_active=True)
        .order_by(Passport.valid_until.desc())
        .first()
    )
    if not passport:
        return 0

    prep_date = subtract_months(passport.valid_until, 3)
    rule_key = f"passport-preparation:{passport.id}:{passport.valid_until.isoformat()}"
    name = get_current_name(employment.person) or "Сотрудник"
    _upsert_rule_event(
        company_id=employment.company_id,
        employment_id=employment.id,
        rule_key=rule_key,
        title=f"Подготовка документов для паспорта: {name}",
        event_type=EventType.PASSPORT,
        event_date=prep_date,
        description=f"Паспорт действителен до {passport.valid_until.isoformat()}",
        reference_type="passport",
        reference_id=passport.id,
    )
    return 1


def run_rule_engine(company_id: int | None = None) -> dict[str, int]:
    query = Employment.query.filter_by(status=EmploymentStatus.ACTIVE.value)
    if company_id:
        query = query.filter_by(company_id=company_id)

    stats = {"contracts": 0, "grades": 0, "passports": 0}
    for employment in query.all():
        stats["contracts"] += process_contract_rules(employment)
        stats["grades"] += process_grade_rules(employment)
        stats["passports"] += process_passport_rules(employment)

    db.session.commit()
    return stats
