from datetime import date

from app.extensions import db
from app.models import Event, EventStatus, EventType
from app.services.events import create_manual_event


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


def test_create_event_hr(admin_client, seed_company):
    response = admin_client.post(
        "/api/events",
        json={
            "company_id": seed_company.id,
            "title": "New event",
            "event_type": "manual",
            "event_date": "2026-07-24",
            "description": "Test",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["title"] == "New event"
    assert payload["status"] == EventStatus.PLANNED.value


def test_overdue_refresh_on_list(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))

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
    assert overdue["status"] == EventStatus.OVERDUE.value
