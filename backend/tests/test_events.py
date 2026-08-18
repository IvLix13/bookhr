from datetime import date

import pytest

from app.extensions import db
from app.models import Event, EventStatus, EventStatusHistory, EventType
from app.services.events import (
    InvalidEventTransition,
    create_manual_event,
    effective_event_status,
    transition_event_status,
)


def test_list_events_filters_by_day(admin_client, seed_company):
    create_manual_event(
        company_id=seed_company.id,
        title="Day event",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
    )
    create_manual_event(
        company_id=seed_company.id,
        title="Other day",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 25),
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/events?company_id={seed_company.id}&from=2026-07-24&to=2026-07-24"
    )
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Day event"


def test_complete_event_hr_only(hr_client, seed_company):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Complete me",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
    )
    db.session.commit()

    response = hr_client.post(
        f"/api/events/{event.id}/complete",
        json={"comment": "Done"},
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["status"] == EventStatus.COMPLETED.value
    assert payload["completion_comment"] == "Done"


def test_complete_event_viewer_forbidden(viewer_client, seed_company):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Protected",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
    )
    db.session.commit()

    response = viewer_client.post(f"/api/events/{event.id}/complete", json={})
    assert response.status_code == 403


def test_get_event_returns_detail(admin_client, seed_company):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Detail event",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
        description="Details here",
    )
    db.session.commit()

    response = admin_client.get(f"/api/events/{event.id}")
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["id"] == event.id
    assert payload["title"] == "Detail event"
    assert payload["description"] == "Details here"
    assert payload["status"] == EventStatus.PLANNED.value


def test_get_event_not_found(admin_client):
    response = admin_client.get("/api/events/999999")
    assert response.status_code == 404


def test_reopen_event_hr(hr_client, seed_company):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Reopen me",
        event_type=EventType.MANUAL,
        event_date=date(2030, 7, 24),
    )
    transition_event_status(event, EventStatus.COMPLETED, "done")
    db.session.commit()

    response = hr_client.post(f"/api/events/{event.id}/reopen", json={})
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["status"] == EventStatus.PLANNED.value


def test_create_event_hr(admin_client, seed_company):
    response = admin_client.post(
        "/api/events",
        json={
            "company_id": seed_company.id,
            "title": "New event",
            "event_type": "manual",
            "event_date": "2030-07-24",
            "description": "Test",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["title"] == "New event"
    assert payload["status"] == EventStatus.PLANNED.value
    assert payload["effective_status"] == EventStatus.PLANNED.value


@pytest.mark.parametrize(
    ("from_status", "to_status", "ok"),
    [
        (EventStatus.PLANNED, EventStatus.COMPLETED, True),
        (EventStatus.PLANNED, EventStatus.CANCELLED, True),
        (EventStatus.PLANNED, EventStatus.OVERDUE, True),
        (EventStatus.OVERDUE, EventStatus.COMPLETED, True),
        (EventStatus.OVERDUE, EventStatus.CANCELLED, True),
        (EventStatus.OVERDUE, EventStatus.PLANNED, True),
        (EventStatus.COMPLETED, EventStatus.PLANNED, True),
        (EventStatus.CANCELLED, EventStatus.PLANNED, True),
        (EventStatus.CANCELLED, EventStatus.COMPLETED, False),
        (EventStatus.COMPLETED, EventStatus.CANCELLED, False),
        (EventStatus.COMPLETED, EventStatus.OVERDUE, False),
        (EventStatus.CANCELLED, EventStatus.OVERDUE, False),
    ],
)
def test_transition_matrix(app, seed_company, from_status, to_status, ok):
    with app.app_context():
        event = create_manual_event(
            company_id=seed_company.id,
            title="Transition",
            event_type=EventType.MANUAL,
            event_date=date(2026, 7, 24),
        )
        db.session.flush()
        if from_status != EventStatus.PLANNED:
            event.status = from_status.value
            db.session.flush()

        if ok:
            transition_event_status(event, to_status, "test")
            assert event.status == to_status.value
        else:
            with pytest.raises(InvalidEventTransition):
                transition_event_status(event, to_status, "test")


def test_same_status_is_noop_without_history(app, seed_company):
    with app.app_context():
        event = create_manual_event(
            company_id=seed_company.id,
            title="Noop",
            event_type=EventType.MANUAL,
            event_date=date(2026, 7, 24),
        )
        db.session.commit()
        before = EventStatusHistory.query.filter_by(event_id=event.id).count()
        transition_event_status(event, EventStatus.PLANNED, "again")
        db.session.commit()
        after = EventStatusHistory.query.filter_by(event_id=event.id).count()
        assert after == before


def test_complete_cancelled_event_returns_409(admin_client, seed_company):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Cancelled",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
    )
    transition_event_status(event, EventStatus.CANCELLED, "cancel")
    db.session.commit()

    response = admin_client.post(f"/api/events/{event.id}/complete", json={})
    assert response.status_code == 409


def test_effective_status_on_list_without_db_write(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.api.serializers.today_moscow", lambda: date(2026, 7, 24))

    event = create_manual_event(
        company_id=seed_company.id,
        title="Overdue event",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 1),
    )
    db.session.commit()
    assert event.status == EventStatus.PLANNED.value

    response = admin_client.get(f"/api/events?company_id={seed_company.id}")
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    overdue = next(item for item in items if item["id"] == event.id)
    assert overdue["status"] == EventStatus.PLANNED.value
    assert overdue["effective_status"] == EventStatus.OVERDUE.value

    db.session.refresh(event)
    assert event.status == EventStatus.PLANNED.value


def test_filter_status_overdue_includes_virtual(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.api.serializers.today_moscow", lambda: date(2026, 7, 24))

    create_manual_event(
        company_id=seed_company.id,
        title="Past planned",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 1),
    )
    create_manual_event(
        company_id=seed_company.id,
        title="Future planned",
        event_type=EventType.MANUAL,
        event_date=date(2026, 8, 1),
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/events?company_id={seed_company.id}&status=overdue"
    )
    assert response.status_code == 200
    titles = {item["title"] for item in response.get_json()["data"]["items"]}
    assert "Past planned" in titles
    assert "Future planned" not in titles


def test_effective_event_status_helper(app, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))
    with app.app_context():
        event = create_manual_event(
            company_id=seed_company.id,
            title="Helper",
            event_type=EventType.MANUAL,
            event_date=date(2026, 7, 1),
        )
        db.session.flush()
        assert effective_event_status(event) == EventStatus.OVERDUE.value
        event.status = EventStatus.COMPLETED.value
        assert effective_event_status(event) == EventStatus.COMPLETED.value


def test_invalid_event_date_returns_json_400(admin_client):
    response = admin_client.get("/api/events?from=notadate")
    assert response.status_code == 400
    assert response.is_json
    assert response.get_json()["success"] is False


def test_create_event_missing_title_returns_json_400(admin_client, seed_company):
    response = admin_client.post(
        "/api/events",
        json={"event_date": "2030-01-01"},
    )
    assert response.status_code == 400
    assert response.is_json
    assert response.get_json()["success"] is False


def test_update_manual_event_hr(hr_client, seed_company):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Editable",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
        description="Old",
    )
    db.session.commit()

    response = hr_client.patch(
        f"/api/events/{event.id}",
        json={
            "title": "Updated title",
            "description": "New description",
            "event_date": "2026-08-01",
        },
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["title"] == "Updated title"
    assert payload["description"] == "New description"
    assert payload["event_date"] == "2026-08-01"


def test_update_rule_event_returns_409(hr_client, seed_company, app):
    from app.models import EventSource

    with app.app_context():
        event = create_manual_event(
            company_id=seed_company.id,
            title="Rule event",
            event_type=EventType.CONTRACT,
            event_date=date(2026, 7, 24),
        )
        event.source = EventSource.RULE.value
        db.session.commit()
        event_id = event.id

    response = hr_client.patch(
        f"/api/events/{event_id}",
        json={"title": "Nope"},
    )
    assert response.status_code == 409


def test_delete_manual_event_hr(hr_client, seed_company):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Delete me",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
    )
    db.session.commit()
    event_id = event.id

    response = hr_client.delete(f"/api/events/{event_id}")
    assert response.status_code == 200
    assert db.session.get(Event, event_id) is None


def test_delete_rule_event_returns_409(hr_client, seed_company, app):
    from app.models import EventSource

    with app.app_context():
        event = create_manual_event(
            company_id=seed_company.id,
            title="Rule event",
            event_type=EventType.GRADE,
            event_date=date(2026, 7, 24),
        )
        event.source = EventSource.RULE.value
        db.session.commit()
        event_id = event.id

    response = hr_client.delete(f"/api/events/{event_id}")
    assert response.status_code == 409
    assert db.session.get(Event, event_id) is not None


def test_cancel_event_triggers_recalc(hr_client, seed_company, monkeypatch):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Cancel me",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
    )
    db.session.commit()

    called = {"count": 0}

    def fake_refresh(*, company_id, employment=None):
        called["count"] += 1

    monkeypatch.setattr("app.api.events.refresh_events_after_mutation", fake_refresh)

    response = hr_client.post(f"/api/events/{event.id}/cancel", json={"comment": "No"})
    assert response.status_code == 200
    assert called["count"] == 1


def test_reopen_event_triggers_recalc(hr_client, seed_company, monkeypatch):
    event = create_manual_event(
        company_id=seed_company.id,
        title="Reopen me",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 24),
    )
    transition_event_status(event, EventStatus.COMPLETED, "done")
    db.session.commit()

    called = {"count": 0}

    def fake_refresh(*, company_id, employment=None):
        called["count"] += 1

    monkeypatch.setattr("app.api.events.refresh_events_after_mutation", fake_refresh)

    response = hr_client.post(f"/api/events/{event.id}/reopen", json={})
    assert response.status_code == 200
    assert called["count"] == 1
