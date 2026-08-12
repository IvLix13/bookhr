from datetime import date

from app.extensions import db
from app.models import (
    DeliveryStatus,
    EventType,
    NotificationDelivery,
    NotificationRule,
)
from app.services.employees import create_person_with_employment
from app.services.events import create_manual_event
from app.services.notifications import (
    queue_escalation_for_event,
    queue_notifications_for_event,
)


def test_queue_escalation_when_threshold_reached(app, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr(
        "app.services.notifications.today_moscow", lambda: date(2026, 7, 24)
    )

    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Эскалация Тест",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Overdue for escalation",
            event_type=EventType.MANUAL,
            event_date=date(2026, 7, 1),
            employment_id=employment.id,
        )
        rule = NotificationRule(
            company_id=seed_company.id,
            room_token="room-main",
            escalation_room_token="room-escalation",
            escalation_after_days=7,
            is_enabled=True,
        )
        db.session.add(rule)
        db.session.commit()

        assert queue_escalation_for_event(event, rule) == 1
        assert queue_escalation_for_event(event, rule) == 0  # idempotent

        deliveries = NotificationDelivery.query.filter(
            NotificationDelivery.idempotency_key.like("escalate:%")
        ).all()
        assert len(deliveries) == 1
        assert deliveries[0].recipient == "room-escalation"
        assert deliveries[0].status == DeliveryStatus.PENDING.value


def test_queue_escalation_skipped_below_threshold(app, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr(
        "app.services.notifications.today_moscow", lambda: date(2026, 7, 24)
    )

    with app.app_context():
        event = create_manual_event(
            company_id=seed_company.id,
            title="Slightly overdue",
            event_type=EventType.MANUAL,
            event_date=date(2026, 7, 20),
        )
        rule = NotificationRule(
            company_id=seed_company.id,
            room_token="room-main",
            escalation_room_token="room-escalation",
            escalation_after_days=7,
            is_enabled=True,
        )
        db.session.add(rule)
        db.session.commit()

        assert queue_escalation_for_event(event, rule) == 0
        assert NotificationDelivery.query.count() == 0


def test_queue_notifications_also_queues_escalation(app, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr(
        "app.services.notifications.today_moscow", lambda: date(2026, 7, 24)
    )

    with app.app_context():
        event = create_manual_event(
            company_id=seed_company.id,
            title="Notify and escalate",
            event_type=EventType.REPORT,
            event_date=date(2026, 7, 1),
        )
        rule = NotificationRule(
            company_id=None,
            event_type=None,
            room_token="room-main",
            escalation_room_token="room-escalation",
            escalation_after_days=3,
            is_enabled=True,
        )
        db.session.add(rule)
        db.session.commit()

        created = queue_notifications_for_event(event)
        assert created == 2
        keys = {d.idempotency_key for d in NotificationDelivery.query.all()}
        assert any(key.startswith("notify:") for key in keys)
        assert any(key.startswith("escalate:") for key in keys)


def test_create_notification_rule_with_escalation(admin_client, seed_company):
    response = admin_client.post(
        "/api/notifications/rules",
        json={
            "company_id": seed_company.id,
            "room_token": "room-main",
            "room_name": "Main",
            "escalation_room_token": "room-boss",
            "escalation_after_days": 5,
        },
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["escalation_room_token"] == "room-boss"
    assert payload["escalation_after_days"] == 5


def test_update_notification_rule(admin_client, seed_company):
    created = admin_client.post(
        "/api/notifications/rules",
        json={
            "company_id": seed_company.id,
            "room_token": "room-main",
            "room_name": "Main",
            "is_enabled": True,
            "remind_days_before": 1,
        },
    )
    rule_id = created.get_json()["data"]["id"]

    response = admin_client.patch(
        f"/api/notifications/rules/{rule_id}",
        json={
            "room_name": "Updated",
            "is_enabled": False,
            "remind_days_before": 3,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["room_name"] == "Updated"
    assert payload["is_enabled"] is False
    assert payload["remind_days_before"] == 3
