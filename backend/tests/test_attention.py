from datetime import date

from app.extensions import db
from app.models import EmployeeGradeHistory, EventType, GradeCatalog, TenureAward
from app.services.employees import create_person_with_employment
from app.services.events import create_manual_event


def test_attention_summary_overdue_events(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.attention.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 7, 24))

    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Иван Иванов",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    event = create_manual_event(
        company_id=seed_company.id,
        title="Overdue task",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 1),
        employment_id=employment.id,
    )
    db.session.commit()
    assert event.status == "planned"

    response = admin_client.get(f"/api/attention?company_id={seed_company.id}&categories=events")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["counts"]["events"] >= 1
    assert any(item["category"] == "events" for item in data["items"])

    db.session.refresh(event)
    assert event.status == "planned"


def test_attention_summary_pending_tenure(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.attention.today_moscow", lambda: date(2026, 7, 24))

    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Петр Петров",
        hire_date=date(2010, 1, 1),
        title="Аналитик",
    )
    db.session.add(
        TenureAward(
            employment_id=employment.id,
            milestone_years=10,
            milestone_date=date(2020, 1, 1),
            is_received=False,
        )
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/attention?company_id={seed_company.id}&categories=tenure&limit=5"
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["counts"]["tenure"] == 1
    assert data["items"][0]["category"] == "tenure"


def test_attention_excludes_max_grade_without_next(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.attention.today_moscow", lambda: date(2026, 7, 24))

    grade = GradeCatalog(name="Lead", rank=1, min_years=1, is_active=True)
    db.session.add(grade)
    db.session.flush()
    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Максимальный грейд",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    db.session.add(
        EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=grade.id,
            assigned_date=date(2024, 1, 1),
        )
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/attention?company_id={seed_company.id}&categories=grades&limit=5"
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["counts"]["grades"] == 0
    assert data["items"] == []


def test_attention_requires_auth(client):
    response = client.get("/api/attention")
    assert response.status_code in (401, 302)
