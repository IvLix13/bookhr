from datetime import date

from app.extensions import db
from app.models import Employment, Event, EventStatus, EventType, Passport
from app.services.employees import create_person_with_employment, get_active_passport
from app.services.rule_engine import PASSPORT_RULE_PREFIX, process_passport_rules


def test_completing_passport_event_registers_new_passport(hr_client, seed_company, app):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Паспорт Обновлён",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.add(
            Passport(
                person_id=employment.person_id,
                valid_until=date(2026, 9, 1),
                is_active=True,
            )
        )
        db.session.commit()
        process_passport_rules(employment)
        db.session.commit()

        from app.models import Event

        event = Event.query.filter(
            Event.rule_key.like(f"{PASSPORT_RULE_PREFIX}:%"),
            Event.employment_id == employment.id,
        ).one()
        event_id = event.id
        employment_id = employment.id

    response = hr_client.post(
        f"/api/events/{event_id}/complete",
        json={"new_passport_valid_until": "2031-06-01"},
    )
    assert response.status_code == 200

    with app.app_context():
        employment = db.session.get(Employment, employment_id)
        event = db.session.get(Event, event_id)
        active = get_active_passport(employment.person)
        assert active is not None
        assert active.valid_until == date(2031, 6, 1)
        assert active.is_active is True

        old_passports = Passport.query.filter_by(
            person_id=employment.person_id,
            valid_until=date(2026, 9, 1),
        ).all()
        assert len(old_passports) == 1
        assert old_passports[0].is_active is False

        db.session.refresh(event)
        assert event.status == EventStatus.COMPLETED.value


def test_completing_passport_event_requires_new_date(hr_client, seed_company, app):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Паспорт Без Даты",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.add(
            Passport(
                person_id=employment.person_id,
                valid_until=date(2026, 9, 1),
                is_active=True,
            )
        )
        db.session.commit()
        process_passport_rules(employment)
        db.session.commit()

        from app.models import Event

        event = Event.query.filter(
            Event.rule_key.like(f"{PASSPORT_RULE_PREFIX}:%"),
            Event.employment_id == employment.id,
        ).one()

    response = hr_client.post(f"/api/events/{event.id}/complete", json={})
    assert response.status_code == 400
    assert "паспорт" in response.get_json()["message"].lower()


def test_completing_passport_event_rejects_earlier_date(hr_client, seed_company, app):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Паспорт Раньше",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.add(
            Passport(
                person_id=employment.person_id,
                valid_until=date(2026, 9, 1),
                is_active=True,
            )
        )
        db.session.commit()
        process_passport_rules(employment)
        db.session.commit()

        from app.models import Event

        event = Event.query.filter(
            Event.rule_key.like(f"{PASSPORT_RULE_PREFIX}:%"),
            Event.employment_id == employment.id,
        ).one()

    response = hr_client.post(
        f"/api/events/{event.id}/complete",
        json={"new_passport_valid_until": "2026-01-01"},
    )
    assert response.status_code == 400
