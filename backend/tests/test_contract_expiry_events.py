from datetime import date

import pytest

from app.extensions import db
from app.models import Company, Contract, Event, EventStatus, EventStatusHistory
from app.services.employees import create_person_with_employment
from app.services.events import transition_event_status
from app.services.rule_engine import (
    cancel_stale_rule_events,
    contract_expiry_rule_key,
    find_contract_renewal_event,
    recalculate_employment_events,
    run_rule_engine,
)


def create_contract(company_id, *, end_date=date(2027, 12, 1)):
    _, employment = create_person_with_employment(
        company_id=company_id,
        full_name="Иван Иванов",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    contract = Contract(
        employment_id=employment.id,
        start_date=date(2025, 12, 1),
        end_date=end_date,
        term_years=2,
        is_active=True,
    )
    db.session.add(contract)
    db.session.flush()
    return employment, contract


def test_existing_contract_gets_expiry_event_without_duplicates(app, seed_company):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        db.session.commit()
        run_rule_engine(seed_company.id)
        run_rule_engine(seed_company.id)
        db.session.commit()

        expiry = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        assert expiry.event_type == "contract"
        assert expiry.event_date == contract.end_date
        assert expiry.reference_type == "contract"
        assert expiry.reference_id == contract.id
        assert expiry.employment_id == employment.id
        assert expiry.source == "rule"
        assert expiry.title == "Договор до 1 декабря 2027 г.: Иван Иванов"
        assert expiry.status == "planned"
        report = find_contract_renewal_event(contract.id)
        assert report.id != expiry.id
        assert report.event_date == date(2027, 8, 1)


def test_expiry_is_available_in_month_day_and_detail_api(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        expiry_id = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one().id
        db.session.commit()

    for query in (
        "from=2027-12-01&to=2027-12-31",
        "from=2027-12-01&to=2027-12-01",
    ):
        response = hr_client.get(f"/api/events?{query}")
        assert response.status_code == 200
        assert [item["id"] for item in response.get_json()["data"]["items"]] == [expiry_id]
    detail = hr_client.get(f"/api/events/{expiry_id}").get_json()["data"]
    assert detail["employee_name"] == "Иван Иванов"
    assert detail["event_date"] == "2027-12-01"


def test_editing_contract_replaces_old_expiry_on_calendar(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        old_id = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one().id
        contract_id = contract.id
        db.session.commit()

    response = hr_client.patch(
        f"/api/contracts/{contract_id}", json={"end_date": "2028-06-01", "term_years": 2},
    )
    assert response.status_code == 200
    with hr_client.application.app_context():
        assert db.session.get(Event, old_id).status == "cancelled"
        contract = db.session.get(Contract, contract_id)
        new = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        assert new.id != old_id
        assert new.event_date == date(2028, 6, 1)
        assert new.status == "planned"


def test_completing_report_extends_expiry_event(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        old_id = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one().id
        report_id = find_contract_renewal_event(contract.id).id
        contract_id = contract.id
        db.session.commit()

    response = hr_client.post(
        f"/api/events/{report_id}/complete", json={"extension_term_years": 1},
    )
    assert response.status_code == 200
    with hr_client.application.app_context():
        contract = db.session.get(Contract, contract_id)
        assert contract.end_date == date(2028, 12, 1)
        assert db.session.get(Event, old_id).status == "cancelled"
        expiry = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        assert expiry.event_date == contract.end_date


def test_completing_expiry_does_not_extend_contract(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        expiry_id = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one().id
        contract_id = contract.id
        db.session.commit()

    response = hr_client.post(
        f"/api/events/{expiry_id}/complete", json={"extension_term_years": 1},
    )
    assert response.status_code == 200
    with hr_client.application.app_context():
        assert db.session.get(Contract, contract_id).end_date == date(2027, 12, 1)
        assert db.session.get(Event, expiry_id).status == EventStatus.COMPLETED.value


@pytest.mark.parametrize("change", ["dismissed", "inactive_contract"])
def test_expiry_cancelled_when_contract_no_longer_current(app, seed_company, change):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        expiry = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        if change == "dismissed":
            employment.status = "dismissed"
        else:
            contract.is_active = False
        recalculate_employment_events(employment)
        assert expiry.status == "cancelled"
        recalculate_employment_events(employment)
        assert expiry.status == "cancelled"


@pytest.mark.parametrize(
    ("end_date", "expected_status"),
    [
        (date(2027, 12, 1), "planned"),
        (date(2026, 10, 13), "planned"),
        (date(2026, 10, 12), "overdue"),
    ],
)
def test_recalculation_restores_current_auto_cancelled_expiry(
    hr_client, seed_company, monkeypatch, end_date, expected_status,
):
    monkeypatch.setattr("app.services.rule_engine.today_moscow", lambda: date(2026, 10, 13))
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 10, 13))
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id, end_date=end_date)
        recalculate_employment_events(employment)
        expiry = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        expiry_id = expiry.id
        # Reproduce a recalculation that omitted the current expiry key.
        cancel_stale_rule_events(employment, {find_contract_renewal_event(contract.id).rule_key})
        db.session.commit()
        assert expiry.status == "cancelled"

        recalculate_employment_events(employment)
        db.session.commit()
        assert expiry.status == expected_status
        history_count = EventStatusHistory.query.filter_by(event_id=expiry_id).count()
        recalculate_employment_events(employment)
        db.session.commit()
        assert EventStatusHistory.query.filter_by(event_id=expiry_id).count() == history_count
        assert Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one().id == expiry_id
        assert EventStatusHistory.query.filter_by(
            event_id=expiry_id, old_status="cancelled", new_status="planned",
        ).count() == 1

    response = hr_client.get(f"/api/events?from={end_date.isoformat()}&to={end_date.isoformat()}")
    assert response.status_code == 200
    assert [(item["id"], item["status"]) for item in response.get_json()["data"]["items"]] == [
        (expiry_id, expected_status),
    ]


@pytest.mark.parametrize("reason", ["manual", "missing_history", "completed", "manual_after_auto"])
def test_recalculation_preserves_explicit_or_unverified_expiry_status(app, seed_company, reason):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        expiry = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        if reason == "missing_history":
            expiry.status = "cancelled"
        elif reason == "completed":
            transition_event_status(expiry, EventStatus.COMPLETED, "Done")
        else:
            if reason == "manual_after_auto":
                transition_event_status(expiry, EventStatus.CANCELLED, "Superseded by recalculation")
                db.session.flush()
                transition_event_status(expiry, EventStatus.PLANNED, "Reopened")
                db.session.flush()
            transition_event_status(expiry, EventStatus.CANCELLED, "HR cancelled this event")
        db.session.commit()
        expected_status = expiry.status
        run_rule_engine(seed_company.id)
        db.session.commit()
        assert expiry.status == expected_status


def test_returning_to_original_contract_date_restores_only_matching_expiry(app, seed_company):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        original = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        contract.end_date = date(2028, 6, 1)
        recalculate_employment_events(employment)
        replacement = Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one()
        assert original.status == "cancelled"
        assert replacement.status == "planned"

        contract.end_date = date(2027, 12, 1)
        recalculate_employment_events(employment)
        db.session.commit()
        assert original.status == "planned"
        assert replacement.status == "cancelled"
        assert Event.query.filter_by(rule_key=contract_expiry_rule_key(contract)).one().id == original.id


def test_expiry_api_excludes_other_company(hr_client, seed_company):
    with hr_client.application.app_context():
        company = Company(name="Other company")
        db.session.add(company)
        db.session.flush()
        employment, _ = create_contract(company.id)
        recalculate_employment_events(employment)
        db.session.commit()
    response = hr_client.get("/api/events?from=2027-12-01&to=2027-12-31")
    assert response.get_json()["data"]["items"] == []
