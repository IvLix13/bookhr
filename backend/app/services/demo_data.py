"""Demo dataset for pilot testing."""

from __future__ import annotations

import uuid
from datetime import date

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import (
    Company,
    Contract,
    EducationStatus,
    Employment,
    Event,
    EventType,
    GradeCatalog,
    Passport,
    Person,
    TenureAward,
)
from app.services.employees import create_person_with_employment
from app.services.events import create_manual_event
from app.services.grades import assign_grade_to_employment
from app.services.rule_engine import run_rule_engine
from app.services.tenure import ensure_tenure_awards
from app.utils.dates import today_moscow


DEMO_GRADES = [
    ("Стажер", 1, 0.5),
    ("Джун", 2, 1.0),
    ("Мидл", 3, 1.5),
    ("Сеньор", 4, 2.0),
    ("Тимлид", 5, 3.0),
]


def _ensure_demo_grades() -> None:
    for name, rank, years in DEMO_GRADES:
        if not GradeCatalog.query.filter_by(rank=rank).first():
            db.session.add(GradeCatalog(name=name, rank=rank, min_years=years))
    db.session.flush()


def _grade_id(name: str) -> int:
    grade = GradeCatalog.query.filter_by(name=name).first()
    if not grade:
        raise RuntimeError(f"Grade not found: {name}")
    return grade.id


DEMO_UUIDS = [
    uuid.UUID("11111111-1111-4111-8111-111111111111"),
    uuid.UUID("22222222-2222-4222-8222-222222222222"),
    uuid.UUID("33333333-3333-4333-8333-333333333333"),
    uuid.UUID("44444444-4444-4444-8444-444444444444"),
    uuid.UUID("55555555-5555-4555-8555-555555555555"),
]


def clear_demo_data(company_id: int) -> None:
    from app.models import Event, EventStatusHistory, NotificationDelivery, Person, PersonNameHistory, PositionHistory

    employments = Employment.query.filter_by(company_id=company_id).all()
    employment_ids = [item.id for item in employments]

    company_events = Event.query.filter_by(company_id=company_id).all()
    event_ids = [item.id for item in company_events]
    if event_ids:
        NotificationDelivery.query.filter(NotificationDelivery.event_id.in_(event_ids)).delete(
            synchronize_session=False
        )
        EventStatusHistory.query.filter(EventStatusHistory.event_id.in_(event_ids)).delete(
            synchronize_session=False
        )
        Event.query.filter(Event.id.in_(event_ids)).delete(synchronize_session=False)

    if employment_ids:
        Contract.query.filter(Contract.employment_id.in_(employment_ids)).delete(synchronize_session=False)
        EmployeeGradeHistory.query.filter(
            EmployeeGradeHistory.employment_id.in_(employment_ids)
        ).delete(synchronize_session=False)
        TenureAward.query.filter(TenureAward.employment_id.in_(employment_ids)).delete(synchronize_session=False)
        PositionHistory.query.filter(PositionHistory.employment_id.in_(employment_ids)).delete(
            synchronize_session=False
        )
        Employment.query.filter(Employment.id.in_(employment_ids)).delete(synchronize_session=False)

    demo_persons = Person.query.filter(Person.uuid.in_(DEMO_UUIDS)).all()
    demo_person_ids = [item.id for item in demo_persons]
    if demo_person_ids:
        Passport.query.filter(Passport.person_id.in_(demo_person_ids)).delete(synchronize_session=False)
        PersonNameHistory.query.filter(PersonNameHistory.person_id.in_(demo_person_ids)).delete(
            synchronize_session=False
        )
        Person.query.filter(Person.id.in_(demo_person_ids)).delete(synchronize_session=False)

    db.session.commit()


def seed_demo_data(force: bool = False) -> dict[str, int]:
    """Load pilot demo employees and related records."""
    today = today_moscow()
    company = Company.query.filter_by(name="Пилотная компания").first()
    if not company:
        raise RuntimeError("Run `flask seed` first")

    if not force and Employment.query.filter_by(company_id=company.id).count() > 0:
        return {"skipped": 1}

    if force:
        clear_demo_data(company.id)

    _ensure_demo_grades()

    demo_people = [
        {
            "uuid": DEMO_UUIDS[0],
            "full_name": "Иванов Иван Иванович",
            "title": "Инженер-программист",
            "position_grade": "Мидл",
            "actual_grade": "Мидл",
            "grade_date": date(2024, 3, 15),
            "hire_date": date(2020, 1, 10),
            "education_status": EducationStatus.YES.value,
            "contract_end": today + relativedelta(months=8),
            "passport_until": today + relativedelta(years=4),
        },
        {
            "uuid": DEMO_UUIDS[1],
            "full_name": "Петров Пётр Петрович",
            "title": "Системный аналитик",
            "position_grade": "Сеньор",
            "actual_grade": "Сеньор",
            "grade_date": date(2022, 6, 1),
            "hire_date": date(2016, 5, 20),
            "education_status": EducationStatus.YES.value,
            "contract_end": today + relativedelta(months=4),
            "passport_until": today + relativedelta(months=2),
        },
        {
            "uuid": DEMO_UUIDS[2],
            "full_name": "Сидорова Анна Сергеевна",
            "title": "HR-менеджер",
            "position_grade": "Мидл",
            "actual_grade": "Джун",
            "grade_date": date(2025, 1, 20),
            "hire_date": date(2023, 9, 1),
            "education_status": EducationStatus.YES.value,
            "contract_end": today + relativedelta(months=10),
            "passport_until": today + relativedelta(months=3),
        },
        {
            "uuid": DEMO_UUIDS[3],
            "full_name": "Козлов Алексей Николаевич",
            "title": "Ведущий инженер",
            "position_grade": "Тимлид",
            "actual_grade": "Тимлид",
            "grade_date": date(2020, 2, 1),
            "hire_date": date(2010, 4, 12),
            "education_status": EducationStatus.YES.value,
            "contract_end": today + relativedelta(years=1),
            "passport_until": today + relativedelta(years=2),
        },
        {
            "uuid": DEMO_UUIDS[4],
            "full_name": "Новикова Елена Андреевна",
            "title": "Стажёр отдела кадров",
            "position_grade": "Стажер",
            "actual_grade": "Стажер",
            "grade_date": date(2026, 2, 1),
            "hire_date": date(2026, 2, 1),
            "education_status": EducationStatus.NO.value,
            "contract_end": today + relativedelta(months=6),
            "passport_until": today + relativedelta(years=5),
        },
    ]

    created = 0
    for row in demo_people:
        person, employment = create_person_with_employment(
            company_id=company.id,
            full_name=row["full_name"],
            hire_date=row["hire_date"],
            title=row["title"],
            position_grade_id=_grade_id(row["position_grade"]),
            education_status=row["education_status"],
            person_uuid=row["uuid"],
        )

        db.session.add(
            Contract(
                employment_id=employment.id,
                start_date=row["hire_date"],
                end_date=row["contract_end"],
                is_active=True,
            )
        )

        grade = db.session.get(GradeCatalog, _grade_id(row["actual_grade"]))
        assign_grade_to_employment(
            employment,
            grade,
            row["grade_date"],
            basis="Демо-данные",
        )

        db.session.add(
            Passport(
                person_id=person.id,
                valid_until=row["passport_until"],
                is_active=True,
            )
        )

        awards = ensure_tenure_awards(employment.id, employment.hire_date)
        for award in awards:
            if award.milestone_years == 10 and employment.hire_date.year <= 2016:
                award.is_received = True
                award.received_date = employment.hire_date + relativedelta(years=10)
            if award.milestone_years == 15 and employment.hire_date.year <= 2011:
                award.is_received = True
                award.received_date = employment.hire_date + relativedelta(years=15)

        created += 1

    first_employment = Employment.query.filter_by(company_id=company.id).first()
    if first_employment:
        create_manual_event(
            company_id=company.id,
            title="Подготовить приказ о поощрении",
            event_type=EventType.AWARD,
            event_date=today + relativedelta(days=14),
            description="Демо-событие для календаря",
            employment_id=first_employment.id,
        )

    db.session.commit()
    run_rule_engine(company.id)

    return {
        "employees": created,
        "events": Event.query.filter_by(company_id=company.id).count(),
    }
