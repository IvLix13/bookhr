from datetime import date

from app.extensions import db
from app.models import Company, Contract, Employment, Event, Person, PersonNameHistory
from app.services.employees import create_person_with_employment
from app.services.rule_engine import run_rule_engine


def test_rule_engine_creates_contract_event(app):
    with app.app_context():
        company = Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

        person, employment = create_person_with_employment(
            company_id=company.id,
            full_name="Иван Иванов",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        contract = Contract(
            employment_id=employment.id,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 1),
            is_active=True,
        )
        db.session.add(contract)
        db.session.commit()

        stats = run_rule_engine(company.id)
        assert stats["contracts"] >= 1

        event = Event.query.filter(Event.rule_key.like("contract-renewal-report:%")).first()
        assert event is not None
        assert event.event_date == date(2026, 8, 1)


def test_rehire_keeps_person_uuid(app):
    with app.app_context():
        company = Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

        person, first = create_person_with_employment(
            company_id=company.id,
            full_name="Петр Петров",
            hire_date=date(2018, 1, 1),
            title="Аналитик",
        )
        person_uuid = person.uuid
        first.status = "dismissed"
        db.session.commit()

        second = Employment(
            person_id=person.id,
            company_id=company.id,
            hire_date=date(2024, 1, 1),
            status="active",
        )
        db.session.add(second)
        db.session.commit()

        assert Person.query.filter_by(uuid=person_uuid).count() == 1
        assert Employment.query.filter_by(person_id=person.id).count() == 2
