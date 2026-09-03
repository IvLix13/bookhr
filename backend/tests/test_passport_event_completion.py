from datetime import date

from app.extensions import db
from app.models import Employment, Event, EventStatus, Passport
from app.services.employees import create_person_with_employment, get_active_passport
from app.services.passports import calculate_passport_renewal_date
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

        event = Event.query.filter(
            Event.rule_key.like(f"{PASSPORT_RULE_PREFIX}:%"),
            Event.employment_id == employment.id,
        ).one()
        event_id = event.id
        employment_id = employment.id
        expected_until = calculate_passport_renewal_date(date(2026, 9, 1))

    response = hr_client.post(
        f"/api/events/{event_id}/complete",
        json={"new_passport_valid_until": expected_until.isoformat()},
    )
    assert response.status_code == 200

    with app.app_context():
        employment = db.session.get(Employment, employment_id)
        event = db.session.get(Event, event_id)
        active = get_active_passport(employment.person)
        assert active is not None
        assert active.valid_until == expected_until
        assert active.is_active is True

        old_passports = Passport.query.filter_by(
            person_id=employment.person_id,
            valid_until=date(2026, 9, 1),
        ).all()
        assert len(old_passports) == 1
        assert old_passports[0].is_active is False

        db.session.refresh(event)
        assert event.status == EventStatus.COMPLETED.value


def test_completing_passport_event_without_date_uses_five_years(hr_client, seed_company, app):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Паспорт Авто",
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

        event = Event.query.filter(
            Event.rule_key.like(f"{PASSPORT_RULE_PREFIX}:%"),
            Event.employment_id == employment.id,
        ).one()
        event_id = event.id

    response = hr_client.post(f"/api/events/{event.id}/complete", json={})
    assert response.status_code == 200

    with app.app_context():
        employment = db.session.get(Employment, event.employment_id)
        active = get_active_passport(employment.person)
        assert active.valid_until == date(2031, 9, 1)


def test_completing_passport_event_rejects_non_five_year_extension(
    hr_client, seed_company, app
):
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

        event = Event.query.filter(
            Event.rule_key.like(f"{PASSPORT_RULE_PREFIX}:%"),
            Event.employment_id == employment.id,
        ).one()

    response = hr_client.post(
        f"/api/events/{event.id}/complete",
        json={"new_passport_valid_until": "2032-09-01"},
    )
    assert response.status_code == 400
    assert "1 сентября 2031 г." in response.get_json()["message"]


def test_passport_preparation_event_is_four_months_before_expiry(app, seed_company):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Паспорт Срок",
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

        event = Event.query.filter(
            Event.rule_key.like(f"{PASSPORT_RULE_PREFIX}:%"),
            Event.employment_id == employment.id,
        ).one()
        assert event.event_date == date(2026, 5, 1)
