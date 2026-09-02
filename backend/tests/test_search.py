from datetime import date

from app.extensions import db
from app.models import EventType
from app.services.employees import create_person_with_employment
from app.services.events import create_manual_event


def test_search_finds_employee_and_event(admin_client, seed_company):
    person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Алексей Смирнов",
        hire_date=date(2021, 3, 1),
        title="Разработчик",
    )
    create_manual_event(
        company_id=seed_company.id,
        title="Совещание по проекту",
        event_type=EventType.MANUAL,
        event_date=date(2026, 8, 1),
        employment_id=employment.id,
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/search?company_id={seed_company.id}&q=Смир&limit=10"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["total"] >= 1
    types = {item["type"] for item in data["results"]}
    assert "employee" in types


def test_search_finds_event_by_title(admin_client, seed_company):
    create_manual_event(
        company_id=seed_company.id,
        title="UniqueEventTitleXYZ",
        event_type=EventType.MANUAL,
        event_date=date(2026, 8, 15),
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/search?company_id={seed_company.id}&q=UniqueEvent"
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    event_items = [item for item in data["results"] if item["type"] == "event"]
    assert event_items
    assert event_items[0]["subtitle"] == "15 августа 2026 г."


def test_search_rejects_short_query(admin_client, seed_company):
    response = admin_client.get(f"/api/search?company_id={seed_company.id}&q=a")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False


def test_search_requires_auth(client):
    response = client.get("/api/search?q=test")
    assert response.status_code in (401, 302)
