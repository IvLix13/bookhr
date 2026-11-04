"""Regressions for contract corrections, lifecycle and company boundaries."""
from datetime import date

import pytest

from app.extensions import db
from app.models import Company, Contract, ContractRenewal, Employment, Event, NotificationDelivery, NotificationRule
from app.services.employees import create_person_with_employment, get_active_contract
from app.services.rule_engine import recalculate_employment_events, run_rule_engine


@pytest.fixture()
def contract_cycle(hr_client, seed_company):
    with hr_client.application.app_context():
        _, employee = create_person_with_employment(
            company_id=seed_company.id, full_name="Договор Тест",
            hire_date=date(2020, 1, 1), title="Инженер",
        )
        contract = Contract(employment_id=employee.id, start_date=date(2025, 12, 1),
                            end_date=date(2027, 11, 30), term_years=2, is_active=True)
        db.session.add(contract)
        db.session.flush()
        recalculate_employment_events(employee)
        db.session.commit()
        renewal = ContractRenewal.query.filter_by(source_contract_id=contract.id).one()
        return contract.id, employee.id, renewal.report_event_id, renewal.signing_event_id


def sign(client, cycle, term=3):
    assert client.post(f"/api/events/{cycle[2]}/complete", json={"extension_term_years": term}).status_code == 200
    assert client.post(f"/api/events/{cycle[3]}/complete", json={}).status_code == 200
    with client.application.app_context():
        return ContractRenewal.query.filter_by(source_contract_id=cycle[0]).one().result_contract_id


def correct(client, route, cid, eid, end, term):
    if route == "contract":
        return client.patch(f"/api/contracts/{cid}", json={"end_date": end, "term_years": term})
    return client.patch(f"/api/employees/{eid}", json={"contract_end": end, "contract_term_years": term})


@pytest.mark.parametrize("route", ["contract", "employee"])
@pytest.mark.parametrize("signed", [False, True])
def test_noop_save_preserves_original_start(hr_client, contract_cycle, monkeypatch, route, signed):
    cid, eid, _, _ = contract_cycle
    if signed:
        assert correct(hr_client, "contract", cid, eid, "2028-02-28", 2).status_code == 200
        cid = sign(hr_client, contract_cycle, term=1)
        monkeypatch.setattr("app.services.contracts.today_moscow", lambda: date(2028, 2, 29))
    with hr_client.application.app_context():
        c = db.session.get(Contract, cid)
        original = (c.start_date, c.end_date, c.term_years)
    assert correct(hr_client, route, cid, eid, original[1].isoformat(), original[2]).status_code == 200
    with hr_client.application.app_context():
        c = db.session.get(Contract, cid)
        assert (c.start_date, c.end_date, c.term_years) == original
        if signed:
            assert c.start_date == date(2028, 2, 29)


@pytest.mark.parametrize("route", ["contract", "employee"])
@pytest.mark.parametrize("end", ["2029-11-30", "2031-11-30"])
def test_signed_correction_rejects_overlap_and_gap(hr_client, contract_cycle, monkeypatch, route, end):
    cid = sign(hr_client, contract_cycle)
    monkeypatch.setattr("app.services.contracts.today_moscow", lambda: date(2027, 12, 1))
    response = correct(hr_client, route, cid, contract_cycle[1], end, 3)
    assert response.status_code in (400, 409)
    assert "Начало подписанного договора фиксировано" in response.get_json()["message"]
    with hr_client.application.app_context():
        c = db.session.get(Contract, cid)
        assert (c.start_date, c.end_date, c.term_years) == (date(2027, 12, 1), date(2030, 11, 30), 3)


@pytest.mark.parametrize("route", ["contract", "employee"])
def test_consistent_signed_correction_keeps_chain_and_context(hr_client, contract_cycle, monkeypatch, route):
    cid = sign(hr_client, contract_cycle)
    monkeypatch.setattr("app.services.contracts.today_moscow", lambda: date(2027, 12, 1))
    assert correct(hr_client, route, cid, contract_cycle[1], "2032-11-30", 5).status_code == 200
    with hr_client.application.app_context():
        c = db.session.get(Contract, cid)
        assert (c.start_date, c.end_date, c.term_years) == (date(2027, 12, 1), date(2032, 11, 30), 5)
        assert ContractRenewal.query.filter_by(result_contract_id=cid).one().term_years == 5
    ctx = hr_client.get(f"/api/events/{contract_cycle[3]}").get_json()["data"]["contract_renewal"]
    assert (ctx["new_start_date"], ctx["new_end_date"], ctx["term_years"]) == ("2027-12-01", "2032-11-30", 5)


@pytest.mark.parametrize("activated", [False, True])
def test_cannot_clear_signed_chain_in_employee_form(hr_client, contract_cycle, monkeypatch, activated):
    result_id = sign(hr_client, contract_cycle)
    if activated:
        monkeypatch.setattr("app.services.contracts.today_moscow", lambda: date(2027, 12, 1))
    response = correct(hr_client, "employee", result_id, contract_cycle[1], None, None)
    assert response.status_code == 400
    with hr_client.application.app_context():
        employee = db.session.get(Employment, contract_cycle[1])
        assert get_active_contract(employee).id == (result_id if activated else contract_cycle[0])


@pytest.mark.parametrize("kind", ["foreign", "missing", "dismissed", "duplicate", "pending"])
def test_create_contract_checks_company_status_and_existing_contract(hr_client, seed_company, contract_cycle, kind):
    with hr_client.application.app_context():
        if kind in ("foreign", "dismissed"):
            company_id = seed_company.id
            if kind == "foreign":
                other = Company(name="Другая компания")
                db.session.add(other)
                db.session.flush()
                company_id = other.id
            _, employee = create_person_with_employment(company_id=company_id, full_name="Другой сотрудник",
                hire_date=date(2020, 1, 1), title="Инженер")
            if kind == "dismissed":
                employee.status = "dismissed"
            eid = employee.id
            db.session.commit()
        elif kind == "missing":
            eid = 999999
        else:
            eid = contract_cycle[1]
    if kind == "pending":
        sign(hr_client, contract_cycle)
        with hr_client.application.app_context():
            # Even an inconsistent legacy active flag must not allow another future period.
            db.session.get(Contract, contract_cycle[0]).is_active = False
            db.session.commit()
    with hr_client.application.app_context():
        before = Contract.query.count()
    response = hr_client.post("/api/contracts", json={"employment_id": eid, "end_date": "2030-11-30", "term_years": 3})
    assert response.status_code == (404 if kind in ("foreign", "missing") else 409)
    with hr_client.application.app_context():
        assert Contract.query.count() == before


@pytest.mark.parametrize("late", [False, True])
def test_signing_closes_expiry_preserves_calendar_and_removes_unsent(hr_client, seed_company, contract_cycle, monkeypatch, late):
    with hr_client.application.app_context():
        rule = NotificationRule(company_id=seed_company.id, recipient_user_id="test", event_type="contract")
        db.session.add(rule)
        recalculate_employment_events(db.session.get(Employment, contract_cycle[1]))
        db.session.commit()
        expiry_id = Event.query.filter_by(reference_type="contract", reference_id=contract_cycle[0], event_type="contract").one().id
        assert NotificationDelivery.query.filter_by(event_id=expiry_id).count() == 1
    if late:
        for module in ("contracts", "events", "rule_engine"):
            monkeypatch.setattr(f"app.services.{module}.today_moscow", lambda: date(2027, 12, 2))
    result_id = sign(hr_client, contract_cycle)
    with hr_client.application.app_context():
        run_rule_engine()
        db.session.commit()
        expiry = db.session.get(Event, expiry_id)
        assert (expiry.status, expiry.event_date) == ("completed", date(2027, 11, 30))
        assert NotificationDelivery.query.filter_by(event_id=expiry_id).count() == 0
        result = db.session.get(Contract, result_id)
        assert result.start_date == date(2027, 12, 1)
        assert result.is_active is late
    data = hr_client.get("/api/events?from=2027-11-30&to=2027-11-30").get_json()["data"]["items"]
    assert any(item["id"] == expiry_id and item["effective_status"] == "completed" for item in data)


def test_signing_preserves_manual_expiry_cancellation(hr_client, contract_cycle):
    with hr_client.application.app_context():
        expiry_id = Event.query.filter_by(reference_type="contract", reference_id=contract_cycle[0], event_type="contract").one().id
    assert hr_client.post(f"/api/events/{expiry_id}/cancel", json={"comment": "Не требуется"}).status_code == 200
    sign(hr_client, contract_cycle)
    with hr_client.application.app_context():
        assert db.session.get(Event, expiry_id).status == "cancelled"
