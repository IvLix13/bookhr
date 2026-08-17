"""Employee service."""

from __future__ import annotations

import uuid
from datetime import date

from app.extensions import db
from app.models import (
    Contract,
    EducationStatus,
    EmployeeGradeHistory,
    Employment,
    EmploymentStatus,
    Event,
    EventStatusHistory,
    GradeCatalog,
    NotificationDelivery,
    Passport,
    Person,
    PersonNameHistory,
    PositionHistory,
    Reward,
    TenureAward,
)
from app.services.audit import log_audit
from app.services.grades import assign_grade_to_employment
from app.utils.dates import calculate_contract_end, calculate_term_years, today_moscow


def get_current_name(person: Person) -> str | None:
    current = (
        PersonNameHistory.query.filter_by(person_id=person.id, valid_to=None)
        .order_by(PersonNameHistory.valid_from.desc())
        .first()
    )
    return current.full_name if current else None


def get_current_position(employment: Employment) -> PositionHistory | None:
    return (
        PositionHistory.query.filter_by(employment_id=employment.id, valid_to=None)
        .order_by(PositionHistory.valid_from.desc())
        .first()
    )


def get_current_grade(employment: Employment) -> EmployeeGradeHistory | None:
    return (
        EmployeeGradeHistory.query.filter_by(employment_id=employment.id, valid_to=None)
        .order_by(EmployeeGradeHistory.assigned_date.desc())
        .first()
    )


def get_active_passport(person: Person) -> Passport | None:
    return (
        Passport.query.filter_by(person_id=person.id, is_active=True)
        .order_by(Passport.valid_until.desc())
        .first()
    )


def get_active_contract(employment: Employment) -> Contract | None:
    return (
        Contract.query.filter_by(employment_id=employment.id, is_active=True)
        .order_by(Contract.end_date.desc())
        .first()
    )


def create_person_with_employment(
    company_id: int,
    full_name: str,
    hire_date: date,
    title: str,
    position_grade_id: int | None = None,
    education_status: str = EducationStatus.UNKNOWN.value,
    person_uuid: uuid.UUID | None = None,
) -> tuple[Person, Employment]:
    person = Person(
        uuid=person_uuid or uuid.uuid4(),
        education_status=education_status,
    )
    db.session.add(person)
    db.session.flush()

    db.session.add(
        PersonNameHistory(
            person_id=person.id,
            full_name=full_name,
            valid_from=hire_date,
        )
    )

    employment = Employment(
        person_id=person.id,
        company_id=company_id,
        hire_date=hire_date,
        status=EmploymentStatus.ACTIVE.value,
    )
    db.session.add(employment)
    db.session.flush()

    db.session.add(
        PositionHistory(
            employment_id=employment.id,
            title=title,
            position_grade_id=position_grade_id,
            valid_from=hire_date,
        )
    )

    log_audit("create", "person", person.id, None, {"full_name": full_name})
    return person, employment


def update_person_name(person: Person, new_name: str, effective_date: date) -> None:
    current = (
        PersonNameHistory.query.filter_by(person_id=person.id, valid_to=None).first()
    )
    old_name = current.full_name if current else None
    if current:
        current.valid_to = effective_date
    db.session.add(
        PersonNameHistory(
            person_id=person.id,
            full_name=new_name,
            valid_from=effective_date,
        )
    )
    log_audit(
        "update",
        "person_name",
        person.id,
        {"full_name": old_name},
        {"full_name": new_name},
    )


def update_position(
    employment: Employment,
    title: str,
    position_grade_id: int | None,
    effective_date: date,
) -> None:
    current = get_current_position(employment)
    if current:
        current.valid_to = effective_date
    db.session.add(
        PositionHistory(
            employment_id=employment.id,
            title=title,
            position_grade_id=position_grade_id,
            valid_from=effective_date,
        )
    )
    log_audit("update", "position", employment.id, None, {"title": title})


def dismiss_employment(
    employment: Employment,
    dismissal_date: date,
    reason: str | None = None,
) -> None:
    employment.status = EmploymentStatus.DISMISSED.value
    employment.dismissal_date = dismissal_date
    employment.dismissal_reason = reason
    log_audit(
        "dismiss",
        "employment",
        employment.id,
        {"status": EmploymentStatus.ACTIVE.value},
        {"status": EmploymentStatus.DISMISSED.value},
    )


def sync_active_contract(
    employment: Employment,
    end_date: date | None = None,
    start_date: date | None = None,
    term_years: float | None = None,
) -> Contract | None:
    contract = get_active_contract(employment)
    contract_start = start_date or (contract.start_date if contract else employment.hire_date)

    if end_date is None and term_years is not None:
        end_date = calculate_contract_end(contract_start, term_years)

    if end_date is None:
        if contract:
            contract.is_active = False
        return None

    if end_date <= contract_start:
        raise ValueError("Дата окончания договора должна быть позже даты начала")

    if term_years is None:
        term_years = calculate_term_years(contract_start, end_date)

    if contract:
        contract.end_date = end_date
        if start_date:
            contract.start_date = start_date
        contract.term_years = term_years
        contract.is_active = True
        return contract

    new_contract = Contract(
        employment_id=employment.id,
        start_date=contract_start,
        end_date=end_date,
        term_years=term_years,
        is_active=True,
    )
    db.session.add(new_contract)
    return new_contract


def sync_actual_grade(
    employment: Employment,
    grade_id: int | None,
    grade_date: date | None,
) -> None:
    current = get_current_grade(employment)
    if grade_id is None or grade_date is None:
        if current:
            current.valid_to = today_moscow()
        return

    if current and current.grade_id == grade_id:
        was_rank_entry = current.rank_started_at == current.assigned_date
        current.assigned_date = grade_date
        if was_rank_entry:
            current.rank_started_at = grade_date
        return

    grade = db.session.get(GradeCatalog, grade_id)
    if not grade:
        raise ValueError("Grade not found")
    assign_grade_to_employment(
        employment,
        grade,
        grade_date,
    )


def sync_passport(person: Person, passport_until: date | None) -> None:
    passport = get_active_passport(person)
    if passport_until is None:
        if passport:
            passport.is_active = False
        return

    if passport:
        passport.valid_until = passport_until
        passport.is_active = True
        return

    db.session.add(
        Passport(
            person_id=person.id,
            valid_until=passport_until,
            is_active=True,
        )
    )


def delete_employment(employment: Employment) -> None:
    """Hard-delete employment and orphaned person records."""
    employment_id = employment.id
    person = employment.person
    person_id = person.id

    event_ids = [
        event.id
        for event in Event.query.filter_by(employment_id=employment_id).all()
    ]
    if event_ids:
        NotificationDelivery.query.filter(
            NotificationDelivery.event_id.in_(event_ids)
        ).delete(synchronize_session=False)
        EventStatusHistory.query.filter(
            EventStatusHistory.event_id.in_(event_ids)
        ).delete(synchronize_session=False)
        Event.query.filter(Event.id.in_(event_ids)).delete(synchronize_session=False)

    Contract.query.filter_by(employment_id=employment_id).delete(synchronize_session=False)
    EmployeeGradeHistory.query.filter_by(employment_id=employment_id).delete(
        synchronize_session=False
    )
    Reward.query.filter_by(employment_id=employment_id).delete(synchronize_session=False)
    PositionHistory.query.filter_by(employment_id=employment_id).delete(
        synchronize_session=False
    )
    db.session.delete(employment)
    db.session.flush()

    remaining = Employment.query.filter_by(person_id=person_id).count()
    if remaining == 0:
        TenureAward.query.filter_by(person_id=person_id).delete(synchronize_session=False)
        Passport.query.filter_by(person_id=person_id).delete(synchronize_session=False)
        PersonNameHistory.query.filter_by(person_id=person_id).delete(
            synchronize_session=False
        )
        db.session.delete(person)

    log_audit("delete", "employment", employment_id, {"person_id": person_id}, None)


def rehire_person(
    person: Person,
    company_id: int,
    hire_date: date,
    title: str,
    position_grade_id: int | None = None,
) -> Employment:
    employment = Employment(
        person_id=person.id,
        company_id=company_id,
        hire_date=hire_date,
        status=EmploymentStatus.ACTIVE.value,
    )
    db.session.add(employment)
    db.session.flush()
    db.session.add(
        PositionHistory(
            employment_id=employment.id,
            title=title,
            position_grade_id=position_grade_id,
            valid_from=hire_date,
        )
    )
    log_audit("rehire", "employment", employment.id, None, {"hire_date": str(hire_date)})
    return employment
