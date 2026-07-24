"""Employee service."""

from __future__ import annotations

import uuid
from datetime import date

from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    EmploymentStatus,
    Passport,
    Person,
    PersonNameHistory,
    PositionHistory,
)
from app.services.audit import log_audit


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
    has_university: bool = False,
    person_uuid: uuid.UUID | None = None,
) -> tuple[Person, Employment]:
    person = Person(uuid=person_uuid or uuid.uuid4(), has_university=has_university)
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
