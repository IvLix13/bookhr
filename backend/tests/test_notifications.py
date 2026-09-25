from datetime import date
from types import SimpleNamespace

import requests

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
from app.services.nextcloud import NextcloudUser, search_users, send_direct_message


def test_nextcloud_26_creates_direct_conversation_and_sends_message(app, monkeypatch):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if len(calls) == 1 and not getattr(request, "retried", False):
            request.retried = True
            raise requests.ConnectionError("temporary")
        if url.endswith("/api/v4/room"):
            return SimpleNamespace(
                status_code=201,
                text='{"ocs":{"data":{"token":"direct-room"}}}',
                json=lambda: {"ocs": {"data": {"token": "direct-room"}}},
            )
        return SimpleNamespace(status_code=201, text="created")

    monkeypatch.setattr("app.services.nextcloud.requests.request", request)
    with app.app_context():
        app.config.update(
            NEXTCLOUD_BASE_URL="https://nextcloud.internal",
            NEXTCLOUD_USERNAME="bookhr-bot",
            NEXTCLOUD_APP_PASSWORD="app-password",
        )
        code, body = send_direct_message("ivanov", "Тест")

    assert (code, body) == (201, "created")
    assert len(calls) == 3
    _, room_url, room_kwargs = calls[1]
    assert room_url == "https://nextcloud.internal/ocs/v2.php/apps/spreed/api/v4/room"
    assert room_kwargs["data"] == {"roomType": 1, "invite": "ivanov"}
    _, chat_url, chat_kwargs = calls[2]
    assert chat_url.endswith("/ocs/v2.php/apps/spreed/api/v1/chat/direct-room")
    assert chat_kwargs["data"] == {"message": "Тест"}
    for _, _, kwargs in calls:
        assert kwargs["auth"] == ("bookhr-bot", "app-password")
        assert kwargs["headers"]["OCS-APIRequest"] == "true"
        assert kwargs["timeout"] == 15
        assert kwargs["verify"] is False


def test_nextcloud_user_search_and_ssl_verification(app, monkeypatch):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        payload = {
            "ocs": {
                "data": [
                    {"id": "ivanov", "label": "Иванов Иван", "source": "users"},
                    {"id": "hr", "label": "HR", "source": "groups"},
                ]
            }
        }
        return SimpleNamespace(status_code=200, text="ok", json=lambda: payload)

    monkeypatch.setattr("app.services.nextcloud.requests.request", request)
    with app.app_context():
        app.config.update(
            NEXTCLOUD_BASE_URL="https://nextcloud.internal",
            NEXTCLOUD_USERNAME="bookhr-bot",
            NEXTCLOUD_APP_PASSWORD="app-password",
            NEXTCLOUD_VERIFY_SSL=True,
        )
        assert search_users("Иванов") == [
            NextcloudUser(user_id="ivanov", display_name="Иванов Иван")
        ]

    assert calls[0][2]["verify"] is True
    assert calls[0][2]["params"] == [
        ("search", "Иванов"),
        ("itemType", "call"),
        ("itemId", "new"),
        ("shareTypes[]", "0"),
    ]


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
            recipient_user_id="user-main",
            escalation_recipient_user_id="user-escalation",
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
        assert deliveries[0].recipient == "user-escalation"
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
            recipient_user_id="user-main",
            escalation_recipient_user_id="user-escalation",
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
            recipient_user_id="user-main",
            escalation_recipient_user_id="user-escalation",
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
            "recipient_user_id": "user-main",
            "recipient_display_name": "Иванов Иван",
            "escalation_recipient_user_id": "user-boss",
            "escalation_recipient_display_name": "Петров Пётр",
            "escalation_after_days": 5,
        },
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["escalation_recipient_user_id"] == "user-boss"
    assert payload["escalation_recipient_display_name"] == "Петров Пётр"
    assert payload["escalation_after_days"] == 5


def test_search_nextcloud_users_api(admin_client, monkeypatch):
    monkeypatch.setattr(
        "app.api.notifications.search_users",
        lambda query: [
            NextcloudUser(user_id="ivanov", display_name=f"{query} Иван")
        ],
    )

    response = admin_client.get("/api/notifications/nextcloud-users?q=Иванов")

    assert response.status_code == 200
    assert response.get_json()["data"] == [
        {"user_id": "ivanov", "display_name": "Иванов Иван"}
    ]


def test_search_nextcloud_users_requires_two_characters(admin_client):
    response = admin_client.get("/api/notifications/nextcloud-users?q=И")
    assert response.status_code == 400


def test_update_notification_rule(admin_client, seed_company):
    created = admin_client.post(
        "/api/notifications/rules",
        json={
            "company_id": seed_company.id,
            "recipient_user_id": "user-main",
            "recipient_display_name": "Иванов Иван",
            "is_enabled": True,
            "remind_days_before": 1,
        },
    )
    rule_id = created.get_json()["data"]["id"]

    response = admin_client.patch(
        f"/api/notifications/rules/{rule_id}",
        json={
            "recipient_display_name": "Иванов И. И.",
            "is_enabled": False,
            "remind_days_before": 3,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["recipient_display_name"] == "Иванов И. И."
    assert payload["is_enabled"] is False
    assert payload["remind_days_before"] == 3


def test_cannot_enable_migrated_rule_without_recipient(
    admin_client, seed_company
):
    with admin_client.application.app_context():
        rule = NotificationRule(
            company_id=seed_company.id,
            recipient_user_id=None,
            is_enabled=False,
        )
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id

    response = admin_client.patch(
        f"/api/notifications/rules/{rule_id}", json={"is_enabled": True}
    )
    assert response.status_code == 400


def test_notification_rules_allowed_for_hr(hr_client, seed_company):
    listed = hr_client.get("/api/notifications/rules")
    assert listed.status_code == 200

    created = hr_client.post(
        "/api/notifications/rules",
        json={
            "recipient_user_id": "user-main",
            "recipient_display_name": "Иванов Иван",
        },
    )
    assert created.status_code == 201
