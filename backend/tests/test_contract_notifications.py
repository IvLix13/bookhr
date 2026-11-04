"""Moving contract stages replaces unsent reminders without losing sent history."""
from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from app.extensions import db
from app.models import Contract, ContractRenewal, Employment, Event, NotificationDelivery, NotificationRule
from app.services.employees import create_person_with_employment
from app.services.notifications import process_pending_notifications
from app.services.rule_engine import recalculate_employment_events


@pytest.fixture()
def reminder_cycle(hr_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.notifications.utcnow", lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    with hr_client.application.app_context():
        _, employee = create_person_with_employment(company_id=seed_company.id, full_name="Напоминание Тест",
            hire_date=date(2020, 1, 1), title="Инженер")
        db.session.add(NotificationRule(company_id=seed_company.id, recipient_user_id="test", send_time_moscow="00:00"))
        contract = Contract(employment_id=employee.id, start_date=date(2025, 12, 1),
                            end_date=date(2027, 11, 30), term_years=2, is_active=True)
        db.session.add(contract)
        db.session.flush()
        recalculate_employment_events(employee)
        db.session.commit()
        renewal = ContractRenewal.query.filter_by(source_contract_id=contract.id).one()
        return contract.id, employee.id, renewal.report_event_id, renewal.signing_event_id


@pytest.mark.parametrize("route", ["event", "contract"])
def test_manual_report_move_replaces_pending_failed_and_keeps_sent(hr_client, reminder_cycle, monkeypatch, route):
    cid, eid, report, _ = reminder_cycle
    with hr_client.application.app_context():
        old = NotificationDelivery.query.filter_by(event_id=report).one()
        old.status = "failed"
        old.attempt_count = 2
        old_key = old.idempotency_key
        sent = NotificationDelivery(event_id=report, rule_id=old.rule_id, recipient="test", status="sent",
            idempotency_key="sent-history", sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        escalation = NotificationDelivery(event_id=report, rule_id=old.rule_id, recipient="boss", status="pending",
            idempotency_key=f"escalate:{report}:{old.rule_id}:1")
        db.session.add_all([sent, escalation])
        db.session.commit()
        sent_id = sent.id
    if route == "event":
        response = hr_client.patch(f"/api/events/{report}", json={"event_date": "2028-01-10"})
    else:
        response = hr_client.patch(f"/api/contracts/{cid}", json={"report_date": "2028-01-10"})
    assert response.status_code == 200
    with hr_client.application.app_context():
        assert NotificationDelivery.query.filter_by(idempotency_key=old_key).first() is None
        assert db.session.get(NotificationDelivery, sent_id).status == "sent"
        pending = NotificationDelivery.query.filter_by(event_id=report, status="pending").all()
        assert len(pending) == 1
        assert pending[0].next_attempt_at.date() == date(2028, 1, 10)
        assert not NotificationDelivery.query.filter(NotificationDelivery.idempotency_key.like("escalate:%")).all()
        count = NotificationDelivery.query.count()
        recalculate_employment_events(db.session.get(Employment, eid))
        db.session.commit()
        assert NotificationDelivery.query.count() == count
        monkeypatch.setattr("app.services.notifications.utcnow", lambda: datetime(2027, 7, 30, tzinfo=timezone.utc))
        send = Mock(return_value=(201, "ok"))
        monkeypatch.setattr("app.services.notifications.send_direct_message", send)
        assert process_pending_notifications()["sent"] == 0
        send.assert_not_called()


def test_contract_end_move_reschedules_report_and_signing(hr_client, reminder_cycle):
    cid, _, report, signing = reminder_cycle
    response = hr_client.patch(f"/api/contracts/{cid}", json={"end_date": "2028-02-29", "term_years": 2})
    assert response.status_code == 200
    with hr_client.application.app_context():
        for event_id, expected in ((report, date(2027, 10, 29)), (signing, date(2028, 2, 29))):
            deliveries = NotificationDelivery.query.filter_by(event_id=event_id).all()
            assert len(deliveries) == 1
            assert deliveries[0].next_attempt_at.date() == expected


def test_sender_skips_legacy_stale_delivery_before_rules_run(hr_client, reminder_cycle, monkeypatch):
    _, _, report, _ = reminder_cycle
    with hr_client.application.app_context():
        old = NotificationDelivery.query.filter_by(event_id=report).one()
        old.next_attempt_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        old_key = old.idempotency_key
        db.session.get(Event, report).event_date = date(2028, 1, 10)
        db.session.commit()
        send = Mock(return_value=(201, "ok"))
        monkeypatch.setattr("app.services.notifications.send_direct_message", send)
        assert process_pending_notifications()["sent"] == 0
        send.assert_not_called()
        db.session.commit()
        assert NotificationDelivery.query.filter_by(idempotency_key=old_key).first() is None


def test_rules_repair_preexisting_stale_queue(hr_client, reminder_cycle):
    _, eid, report, _ = reminder_cycle
    with hr_client.application.app_context():
        event = db.session.get(Event, report)
        event.event_date = date(2028, 1, 10)
        event.manual_date = True
        db.session.commit()
    assert hr_client.application.test_cli_runner().invoke(args=["run-rules"]).exit_code == 0
    with hr_client.application.app_context():
        deliveries = NotificationDelivery.query.filter_by(event_id=report).all()
        assert len(deliveries) == 1
        assert deliveries[0].next_attempt_at.date() == date(2028, 1, 10)
