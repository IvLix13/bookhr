from datetime import date, datetime, timezone
from unittest.mock import Mock

from app.extensions import db
from app.models import NotificationDelivery, NotificationRule
from app.services.attestations import find_attestation_events, set_attestation_date
from app.services.employees import create_person_with_employment
from app.services.notifications import process_pending_notifications


def test_move_replaces_pending_and_failed_deliveries_preserving_sent_log(
    app, seed_company, monkeypatch
):
    clock = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.notifications.utcnow", lambda: clock)
    with app.app_context():
        rule = NotificationRule(
            company_id=seed_company.id,
            recipient_user_id="hr",
            send_time_moscow="00:00",
            remind_days_before=0,
        )
        db.session.add(rule)
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Иван Иванов",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        set_attestation_date(employment, date(2026, 10, 30))
        db.session.flush()
        deliveries = NotificationDelivery.query.order_by(NotificationDelivery.id).all()
        assert len(deliveries) == 2
        events = find_attestation_events(employment)
        prep_delivery = next(
            delivery
            for delivery in deliveries
            if delivery.event_id == events["attestation_preparation"].id
        )
        prep_delivery.status = "failed"
        prep_delivery.attempt_count = 1
        conduct_delivery = next(
            delivery
            for delivery in deliveries
            if delivery.event_id == events["attestation"].id
        )
        conduct_delivery.status = "sent"
        sent_id = conduct_delivery.id
        old_prep_key = prep_delivery.idempotency_key
        db.session.commit()

        set_attestation_date(employment, date(2026, 11, 6))
        db.session.commit()
        deliveries = NotificationDelivery.query.all()
        assert len(deliveries) == 3  # Old sent history plus the new pair.
        assert db.session.get(NotificationDelivery, sent_id).status == "sent"
        assert not NotificationDelivery.query.filter_by(
            idempotency_key=old_prep_key
        ).first()
        pending = [delivery for delivery in deliveries if delivery.status == "pending"]
        assert {delivery.next_attempt_at.date() for delivery in pending} == {
            date(2026, 10, 23),
            date(2026, 11, 6),
        }

        # The old preparation due date no longer triggers an early send.
        clock = datetime(2026, 10, 16, 10, tzinfo=timezone.utc)
        send = Mock(return_value=(201, "ok"))
        monkeypatch.setattr("app.services.notifications.send_direct_message", send)
        result = process_pending_notifications()
        assert result["sent"] == 0
        send.assert_not_called()

        # A repeated calculation keeps the existing schedule and count.
        set_attestation_date(employment, date(2026, 11, 6))
        db.session.commit()
        assert NotificationDelivery.query.count() == 3


def test_closed_attestation_does_not_send_waiting_notifications(
    hr_client, seed_company, monkeypatch
):
    with hr_client.application.app_context():
        db.session.add(
            NotificationRule(
                company_id=seed_company.id,
                recipient_user_id="hr",
                send_time_moscow="00:00",
            )
        )
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Иван Иванов",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        set_attestation_date(employment, date(2026, 11, 6))
        db.session.commit()
        ids = {
            kind: event.id
            for kind, event in find_attestation_events(employment).items()
        }
    assert (
        hr_client.post(f"/api/events/{ids['attestation']}/complete").status_code == 200
    )
    assert (
        hr_client.post(
            f"/api/events/{ids['attestation_preparation']}/cancel",
            json={"comment": "Не требуется"},
        ).status_code
        == 200
    )
    with hr_client.application.app_context():
        assert NotificationDelivery.query.count() == 0
        monkeypatch.setattr(
            "app.services.notifications.utcnow",
            lambda: datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        send = Mock(return_value=(201, "ok"))
        monkeypatch.setattr("app.services.notifications.send_direct_message", send)
        assert process_pending_notifications()["sent"] == 0
        send.assert_not_called()
    assert hr_client.post(f"/api/events/{ids['attestation']}/reopen").status_code == 200
    with hr_client.application.app_context():
        deliveries = NotificationDelivery.query.all()
        assert len(deliveries) == 1
        assert deliveries[0].event_id == ids["attestation"]
