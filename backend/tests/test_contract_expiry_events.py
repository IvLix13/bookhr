"""The legacy expiry rule is retired; report and signing remain available."""
from datetime import date

import pytest

from app.extensions import db
from app.models import Company, Contract, Event, EventStatusHistory
from app.services.employees import create_person_with_employment
from app.services.rule_engine import (
    contract_expiry_rule_key,
    find_contract_renewal_event,
    recalculate_employment_events,
    run_rule_engine,
)


def create_contract(company_id):
    _, employment = create_person_with_employment(
        company_id=company_id, full_name="Иван Иванов", hire_date=date(2020, 1, 1), title="Инженер",
    )
    contract = Contract(
        employment_id=employment.id, start_date=date(2025, 12, 1),
        end_date=date(2027, 12, 1), term_years=2, is_active=True,
    )
    db.session.add(contract)
    db.session.flush()
    return employment, contract


def legacy_expiry(contract, *, status="planned", source="rule"):
    event = Event(
        company_id=contract.employment.company_id, employment_id=contract.employment_id,
        event_type="contract", source=source, status=status, event_date=contract.end_date,
        title="Договор до…", reference_type="contract", reference_id=contract.id,
        rule_key=contract_expiry_rule_key(contract) if source == "rule" else None,
    )
    db.session.add(event)
    db.session.flush()
    return event


def test_only_report_and_signing_created_without_duplicates(app, seed_company):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        for _ in range(2):
            stats = run_rule_engine(seed_company.id)
            assert stats["contracts"] == 2
            db.session.commit()
        events = Event.query.filter_by(employment_id=employment.id).all()
        assert {e.event_type for e in events} == {"report", "contract_signing"}
        assert len(events) == 2
        assert find_contract_renewal_event(contract.id).event_date == date(2027, 8, 1)


@pytest.mark.parametrize("status", ["planned", "overdue", "completed", "cancelled"])
def test_legacy_expiry_cancelled_only_if_open(app, seed_company, status):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        old = legacy_expiry(contract, status=status)
        original_period = (contract.start_date, contract.end_date, contract.term_years)
        db.session.commit()
        run_rule_engine(seed_company.id)
        db.session.commit()
        expected = "cancelled" if status in {"planned", "overdue"} else status
        assert old.status == expected
        history_count = EventStatusHistory.query.filter_by(event_id=old.id).count()
        assert history_count == (1 if status in {"planned", "overdue"} else 0)
        if history_count:
            assert EventStatusHistory.query.filter_by(event_id=old.id).one().old_status == status
        run_rule_engine(seed_company.id)
        db.session.commit()
        assert old.status == expected
        assert EventStatusHistory.query.filter_by(event_id=old.id).count() == history_count
        assert Event.query.filter_by(event_type="contract").count() == 1
        assert (contract.start_date, contract.end_date, contract.term_years) == original_period
        assert Event.query.filter_by(event_type="contract_signing", status="planned").count() == 1


def test_manual_contract_event_is_not_cancelled(app, seed_company):
    with app.app_context():
        _, contract = create_contract(seed_company.id)
        manual = legacy_expiry(contract, source="manual")
        run_rule_engine(seed_company.id)
        assert manual.status == "planned"


def test_company_filter_does_not_cancel_other_company(app, seed_company):
    with app.app_context():
        company = Company(name="Other")
        db.session.add(company)
        db.session.flush()
        _, own_contract = create_contract(seed_company.id)
        _, other_contract = create_contract(company.id)
        own = legacy_expiry(own_contract)
        other = legacy_expiry(other_contract)
        run_rule_engine(seed_company.id)
        assert own.status == "cancelled"
        assert other.status == "planned"


def test_calendar_exposes_signing_instead_of_expiry(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        old = legacy_expiry(contract)
        old_id = old.id
        recalculate_employment_events(employment)
        db.session.commit()
    for query in ("from=2027-12-01&to=2027-12-31", "from=2027-12-01&to=2027-12-01"):
        rows = hr_client.get(f"/api/events?{query}").get_json()["data"]["items"]
        assert any(e["event_type"] == "contract_signing" for e in rows)
        assert not any(e["event_type"] == "contract" and e["status"] != "cancelled" for e in rows)
    assert hr_client.get(f"/api/events/{old_id}").get_json()["data"]["status"] == "cancelled"


def test_edit_and_date_restoration_do_not_revive_expiry(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        old = legacy_expiry(contract)
        # Older generator specifically revived this cancellation reason.
        old.status = "cancelled"
        db.session.add(EventStatusHistory(event_id=old.id, old_status="planned", new_status="cancelled",
                                          comment="Superseded by recalculation"))
        recalculate_employment_events(employment)
        cid, old_id = contract.id, old.id
        db.session.commit()
    for end in ("2028-06-01", "2027-12-01"):
        response = hr_client.patch(f"/api/contracts/{cid}", json={"end_date": end, "term_years": 2})
        assert response.status_code == 200
        with hr_client.application.app_context():
            assert db.session.get(Event, old_id).status == "cancelled"
            assert Event.query.filter_by(event_type="contract").count() == 1
            assert Event.query.filter_by(event_type="contract_signing").one().event_date.isoformat() == end


def test_signing_still_creates_successor_without_expiry(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        recalculate_employment_events(employment)
        cid = contract.id
        report_id = find_contract_renewal_event(cid).id
        signing_id = Event.query.filter_by(event_type="contract_signing").one().id
        db.session.commit()
    assert hr_client.post(f"/api/events/{report_id}/complete", json={"extension_term_years": 3}).status_code == 200
    assert hr_client.post(f"/api/events/{signing_id}/complete", json={}).status_code == 200
    with hr_client.application.app_context():
        assert Contract.query.count() == 2
        assert db.session.get(Contract, cid).end_date == date(2027, 12, 1)
        assert Event.query.filter_by(event_type="contract").count() == 0
        assert Event.query.filter_by(event_type="report").count() == 2
        assert Event.query.filter_by(event_type="contract_signing").count() == 2
