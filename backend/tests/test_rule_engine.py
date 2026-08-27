from datetime import date

from app.extensions import db
from app.models import (
    Company,
    Contract,
    EmployeeGradeHistory,
    Employment,
    Event,
    EventSource,
    EventStatus,
    GradeCatalog,
    Passport,
    Person,
)
from app.services.employees import create_person_with_employment
from app.services.grades import compute_grade_eligibility
from app.services.rule_engine import (
    _expected_rule_keys,
    contract_rule_key,
    find_contract_renewal_event,
    grade_preparation_rule_key,
    grade_promotion_rule_key,
    grade_rule_key,
    passport_rule_key,
    process_contract_rules,
    recalculate_employment_events,
    run_rule_engine,
    tenure_award_rule_key,
)
from app.services.tenure import ensure_tenure_awards


def test_rule_engine_creates_contract_event(app):
    with app.app_context():
        company = Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

        _person, employment = create_person_with_employment(
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
        assert event.rule_key == contract_rule_key(contract)


def test_create_contract_triggers_renewal_report(hr_client, seed_company):
    with hr_client.application.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Сергей Сергеев",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.commit()
        employment_id = employment.id

    response = hr_client.post(
        "/api/contracts",
        json={
            "employment_id": employment_id,
            "end_date": "2027-12-01",
            "term_years": 3,
        },
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["renewal_report_event"] is not None
    assert payload["renewal_report_event"]["event_date"] == "2027-08-01"
    assert payload["renewal_report_event"]["status"] == EventStatus.PLANNED.value


def test_completed_renewal_report_is_not_reopened(app):
    with app.app_context():
        company = Company(name="Test Co")
        db.session.add(company)
        db.session.commit()

        _, employment = create_person_with_employment(
            company_id=company.id,
            full_name="Анна Аннова",
            hire_date=date(2020, 1, 1),
            title="Аналитик",
        )
        contract = Contract(
            employment_id=employment.id,
            start_date=date(2025, 1, 1),
            end_date=date(2027, 12, 1),
            is_active=True,
        )
        db.session.add(contract)
        db.session.commit()

        process_contract_rules(employment)
        db.session.commit()
        event = find_contract_renewal_event(contract.id)
        assert event is not None
        completed_id = event.id
        event.status = EventStatus.COMPLETED.value
        db.session.commit()

        process_contract_rules(employment)
        db.session.commit()

        completed = db.session.get(Event, completed_id)
        assert completed is not None
        assert completed.status == EventStatus.COMPLETED.value
        # No open report left, so the completed one is surfaced to keep its date
        # visible on the contracts screen.
        still_found = find_contract_renewal_event(contract.id)
        assert still_found is not None
        assert still_found.id == completed_id

        contract.end_date = date(2028, 6, 1)
        db.session.commit()
        process_contract_rules(employment)
        db.session.commit()

        completed = db.session.get(Event, completed_id)
        assert completed.status == EventStatus.COMPLETED.value
        updated = find_contract_renewal_event(contract.id)
        assert updated is not None
        assert updated.id != completed_id
        assert updated.status == EventStatus.PLANNED.value


def test_rule_key_invariant_matches_generated_events(app):
    with app.app_context():
        company = Company(name="Test Co")
        db.session.add(company)
        grade = GradeCatalog(name="Джун", rank=1, min_years=1, is_active=True)
        next_grade = GradeCatalog(name="Мидл", rank=2, min_years=1.5, is_active=True)
        db.session.add_all([grade, next_grade])
        db.session.commit()

        person, employment = create_person_with_employment(
            company_id=company.id,
            full_name="Инвариант Тестов",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            position_grade_id=next_grade.id,
                education_status="yes",
        )
        contract = Contract(
            employment_id=employment.id,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 1),
            is_active=True,
        )
        history = EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=grade.id,
            assigned_date=date(2025, 1, 1),
        )
        passport = Passport(
            person_id=person.id,
            series_number="1234 567890",
            valid_until=date(2027, 6, 1),
            is_active=True,
        )
        db.session.add_all([contract, history, passport])
        db.session.commit()

        recalculate_employment_events(employment)
        db.session.commit()

        open_keys = {
            event.rule_key
            for event in Event.query.filter_by(
                employment_id=employment.id,
                source=EventSource.RULE.value,
            )
            .filter(Event.status.in_([EventStatus.PLANNED.value, EventStatus.OVERDUE.value]))
            .all()
        }
        expected = _expected_rule_keys(employment)
        assert open_keys == expected

        eligibility = compute_grade_eligibility(employment)
        assert contract_rule_key(contract) in expected
        assert grade_preparation_rule_key(history.id, eligibility["eligible_date"]) in expected
        assert grade_promotion_rule_key(history.id, eligibility["eligible_date"]) in expected
        assert passport_rule_key(passport) in expected

        stats = run_rule_engine(company.id)
        assert stats["cancelled"] == 0


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


def test_rule_engine_creates_tenure_award_event(app, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 1, 1))

    with app.app_context():
        company = Company(name="Tenure Co")
        db.session.add(company)
        db.session.commit()

        _, employment = create_person_with_employment(
            company_id=company.id,
            full_name="Ветеран Ветеранов",
            hire_date=date(2010, 1, 1),
            title="Инженер",
        )
        awards = ensure_tenure_awards(employment.person_id, employment.company_id)
        db.session.commit()
        ten_year_award = next(a for a in awards if a.milestone_years == 10)

        stats = run_rule_engine(company.id)
        assert stats["tenure"] >= 1

        event = Event.query.filter_by(
            rule_key=tenure_award_rule_key(ten_year_award),
        ).first()
        assert event is not None
        assert event.event_type == "award"
        assert event.reference_type == "tenure_award"
        assert event.reference_id == ten_year_award.id
        assert event.event_date == date(2020, 1, 1)
        assert "10 лет" in event.title


def test_rule_engine_creates_tenure_event_for_cumulative_milestone(app, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 1, 1))

    with app.app_context():
        company = Company(name="Tenure Cumulative Co")
        db.session.add(company)
        db.session.commit()

        person, first = create_person_with_employment(
            company_id=company.id,
            full_name="Суммарный Ветеран",
            hire_date=date(2000, 1, 1),
            title="Инженер",
        )
        first.status = "dismissed"
        first.dismissal_date = date(2010, 1, 1)
        second = Employment(
            person_id=person.id,
            company_id=company.id,
            hire_date=date(2020, 1, 1),
            status="active",
        )
        db.session.add(second)
        db.session.commit()

        stats = run_rule_engine(company.id)
        assert stats["tenure"] >= 1

        event = Event.query.filter(
            Event.employment_id == second.id,
            Event.event_type == "award",
        ).first()
        assert event is not None
        assert event.event_date == date(2010, 1, 1)
        assert event.reference_type == "tenure_award"


def test_complete_tenure_award_event_marks_received(hr_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 1, 1))
    monkeypatch.setattr("app.services.event_completion.today_moscow", lambda: date(2026, 1, 1))

    with hr_client.application.app_context():
        from app.models import TenureAward

        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Награда Событие",
            hire_date=date(2010, 1, 1),
            title="Инженер",
        )
        awards = ensure_tenure_awards(employment.person_id, employment.company_id)
        db.session.commit()
        award = next(a for a in awards if a.milestone_years == 10)
        award_id = award.id

        run_rule_engine(seed_company.id)
        db.session.commit()

        event = Event.query.filter_by(
            rule_key=tenure_award_rule_key(award),
        ).first()
        event_id = event.id

    response = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert response.status_code == 200

    with hr_client.application.app_context():
        award = db.session.get(TenureAward, award_id)
        assert award.is_received is True
        assert award.received_date == date(2020, 1, 1)
        event = db.session.get(Event, event_id)
        assert event.status == EventStatus.COMPLETED.value
