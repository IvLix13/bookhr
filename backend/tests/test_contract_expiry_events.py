from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from app.extensions import db
from app.models import Company, Contract, Event, EventStatusHistory, NotificationDelivery, NotificationRule
from app.services.employees import create_person_with_employment
from app.services.notifications import process_pending_notifications
from app.services.rule_engine import (
    _expected_rule_keys, contract_expiry_rule_key, find_contract_renewal_event,
    recalculate_employment_events, retire_contract_expiry_events, run_rule_engine,
)


def create_contract(company_id):
    _, employment = create_person_with_employment(
        company_id=company_id, full_name="Иван Иванов",
        hire_date=date(2020, 1, 1), title="Инженер",
    )
    contract = Contract(employment_id=employment.id, start_date=date(2025, 12, 1),
                        end_date=date(2027, 12, 1), term_years=2, is_active=True)
    db.session.add(contract)
    db.session.flush()
    return employment, contract


def legacy_expiry(employment, contract, status="planned", **overrides):
    values = dict(company_id=employment.company_id, employment_id=employment.id,
                  title="Договор до 1 декабря 2027 г.: Иван Иванов",
                  event_type="contract", event_date=contract.end_date, source="rule",
                  reference_type="contract", reference_id=contract.id,
                  rule_key=contract_expiry_rule_key(contract), status=status)
    values.update(overrides)
    event = Event(**values)
    db.session.add(event)
    db.session.flush()
    return event


def test_contract_has_only_report_and_signing_without_expiry(app, seed_company):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        for _ in range(2):
            assert run_rule_engine(seed_company.id)["contracts"] == 2
            db.session.commit()
        stages = Event.query.filter_by(reference_type="contract", reference_id=contract.id).all()
        assert {event.event_type for event in stages} == {"report", "contract_signing"}
        assert len(stages) == 2
        assert find_contract_renewal_event(contract.id).event_date == date(2027, 8, 1)
        assert contract_expiry_rule_key(contract) not in _expected_rule_keys(employment)


@pytest.mark.parametrize("status", ["planned", "overdue", "completed", "cancelled"])
def test_legacy_expiry_is_cancelled_and_never_revived(app, seed_company, status):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        expiry = legacy_expiry(employment, contract, status=status)
        if status == "completed":
            expiry.completed_at = datetime(2027, 12, 1, tzinfo=timezone.utc)
        db.session.commit()
        assert retire_contract_expiry_events() == (0 if status == "cancelled" else 1)
        db.session.commit()
        history = EventStatusHistory.query.filter_by(event_id=expiry.id).count()
        for _ in range(2):
            recalculate_employment_events(employment)
            run_rule_engine()
            db.session.commit()
        assert expiry.status == "cancelled"
        assert EventStatusHistory.query.filter_by(event_id=expiry.id).count() == history
        assert Event.query.filter_by(event_type="contract", source="rule").count() == 1


def test_legacy_expiry_without_standard_key_is_retired(app, seed_company):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        expiry = legacy_expiry(employment, contract, rule_key="old-contract-rule")
        assert retire_contract_expiry_events(employment_id=employment.id) == 1
        assert expiry.status == "cancelled"


def test_company_scope_includes_dismissed_and_inactive_contracts(app, seed_company):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        expiry = legacy_expiry(employment, contract, status="completed")
        employment.status = "dismissed"
        contract.is_active = False
        other = Company(name="Other company")
        db.session.add(other)
        db.session.flush()
        other_employment, other_contract = create_contract(other.id)
        other_expiry = legacy_expiry(other_employment, other_contract)
        db.session.commit()
        assert run_rule_engine(seed_company.id)["cancelled"] >= 1
        db.session.commit()
        assert expiry.status == "cancelled"
        assert other_expiry.status == "planned"


def test_manual_contract_and_other_rules_are_preserved(app, seed_company):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        manual = legacy_expiry(employment, contract, source="manual")
        report = legacy_expiry(employment, contract, event_type="report", rule_key="other-report")
        assert retire_contract_expiry_events() == 0
        assert manual.status == report.status == "planned"


def test_retirement_removes_unsent_notifications_and_preserves_sent_history(app, seed_company, monkeypatch):
    with app.app_context():
        employment, contract = create_contract(seed_company.id)
        expiry = legacy_expiry(employment, contract)
        rule = NotificationRule(company_id=seed_company.id, recipient_user_id="test", send_time_moscow="00:00")
        db.session.add(rule)
        db.session.flush()
        for status in ("pending", "failed", "sent"):
            db.session.add(NotificationDelivery(event_id=expiry.id, rule_id=rule.id,
                recipient="test", status=status, idempotency_key=f"legacy:{status}",
                next_attempt_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
        db.session.commit()
        run_rule_engine()
        db.session.commit()
        deliveries = NotificationDelivery.query.filter_by(event_id=expiry.id).all()
        assert [row.status for row in deliveries] == ["sent"]
        send = Mock(return_value=(201, "ok"))
        monkeypatch.setattr("app.services.notifications.send_direct_message", send)
        assert process_pending_notifications()["sent"] == 0
        send.assert_not_called()


def test_sender_does_not_send_legacy_expiry_before_rules_run(app, seed_company, monkeypatch):
    with app.app_context():
        from app.services.notifications import queue_notifications_for_event
        employment, contract = create_contract(seed_company.id)
        expiry = legacy_expiry(employment, contract)
        rule = NotificationRule(company_id=seed_company.id, recipient_user_id="test", send_time_moscow="00:00")
        db.session.add(rule)
        db.session.flush()
        db.session.add(NotificationDelivery(event_id=expiry.id, rule_id=rule.id, recipient="test",
            status="pending", idempotency_key="legacy-pending", next_attempt_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
        db.session.commit()
        send = Mock(return_value=(201, "ok"))
        monkeypatch.setattr("app.services.notifications.send_direct_message", send)
        assert process_pending_notifications()["sent"] == 0
        send.assert_not_called()
        assert queue_notifications_for_event(expiry) == 0
        assert NotificationDelivery.query.filter_by(event_id=expiry.id).count() == 0
        assert expiry.status == "planned"  # Retirement itself belongs to run-rules.


def test_edit_report_and_signing_do_not_recreate_expiry(hr_client, seed_company):
    with hr_client.application.app_context():
        employment, contract = create_contract(seed_company.id)
        expiry = legacy_expiry(employment, contract)
        recalculate_employment_events(employment)
        report = find_contract_renewal_event(contract.id)
        from app.models import ContractRenewal
        renewal = ContractRenewal.query.filter_by(source_contract_id=contract.id).one()
        cid, eid, report_id, signing_id = contract.id, expiry.id, report.id, renewal.signing_event_id
        db.session.commit()
    assert hr_client.patch(f"/api/contracts/{cid}", json={"end_date": "2028-06-01", "term_years": 2}).status_code == 200
    assert hr_client.post(f"/api/events/{report_id}/complete", json={"extension_term_years": 3}).status_code == 200
    assert hr_client.post(f"/api/events/{signing_id}/complete", json={}).status_code == 200
    with hr_client.application.app_context():
        assert db.session.get(Event, eid).status == "cancelled"
        assert Event.query.filter_by(event_type="contract", source="rule").count() == 1
    items = hr_client.get("/api/events?from=2028-06-01&to=2028-06-01").get_json()["data"]["items"]
    assert {event["event_type"] for event in items} == {"contract_signing"}


def test_purged_expiry_does_not_return_on_recalculation(app, seed_company):
    with app.app_context():
        from app.services.database_maintenance import purge_cancelled_events
        employment, contract = create_contract(seed_company.id)
        legacy_expiry(employment, contract)
        run_rule_engine()
        db.session.commit()
        assert purge_cancelled_events(apply=True)["events"] == 1
        db.session.commit()
        run_rule_engine()
        db.session.commit()
        assert Event.query.filter_by(event_type="contract", source="rule").count() == 0

