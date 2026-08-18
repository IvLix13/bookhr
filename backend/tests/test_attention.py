from datetime import date

from app.extensions import db
from app.models import EmployeeGradeHistory, Employment, EmploymentStatus, EventType, GradeCatalog, TenureAward
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
    event_items = [item for item in data["items"] if item["category"] == "events"]
    assert event_items
    assert event_items[0]["route"] == f"/?event={event.id}"

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
            person_id=employment.person_id,
            company_id=employment.company_id,
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


def test_attention_excludes_tenure_when_only_cumulative_qualifies(
    admin_client,
    seed_company,
    monkeypatch,
):
    monkeypatch.setattr("app.services.attention.today_moscow", lambda: date(2026, 7, 24))

    person, first = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Суммарный Стаж",
        hire_date=date(2000, 1, 1),
        title="Аналитик",
    )
    first.status = EmploymentStatus.DISMISSED.value
    first.dismissal_date = date(2010, 1, 1)
    second = Employment(
        person_id=person.id,
        company_id=seed_company.id,
        hire_date=date(2020, 1, 1),
        status=EmploymentStatus.ACTIVE.value,
    )
    db.session.add(second)
    db.session.add(
        TenureAward(
            person_id=person.id,
            company_id=seed_company.id,
            milestone_years=10,
            milestone_date=date(2010, 1, 1),
            is_received=False,
        )
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/attention?company_id={seed_company.id}&categories=tenure&limit=5"
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["counts"]["tenure"] == 0
    assert data["items"] == []


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


def test_attention_grade_items_link_to_related_event(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.attention.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.services.grades.today_moscow", lambda: date(2026, 7, 24))

    junior = GradeCatalog(name="Junior", rank=1, min_years=1.5, is_active=True)
    middle = GradeCatalog(name="Middle", rank=2, min_years=2, is_active=True)
    db.session.add_all([junior, middle])
    db.session.flush()
    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Грейд Событие",
        hire_date=date(2020, 1, 1),
        title="Инженер",
        position_grade_id=middle.id,
        education_status="yes",
    )
    db.session.add(
        EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=junior.id,
            assigned_date=date(2025, 1, 24),
        )
    )
    event = create_manual_event(
        company_id=seed_company.id,
        title="Рассмотреть повышение грейда",
        event_type=EventType.GRADE,
        event_date=date(2026, 7, 10),
        employment_id=employment.id,
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/attention?company_id={seed_company.id}&categories=grades&limit=5"
    )
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert items
    assert items[0]["category"] == "grades"
    assert items[0]["id"] == event.id
    assert items[0]["route"] == f"/?event={event.id}"
    assert "/grades" not in (items[0]["route"] or "")


def test_attention_requires_auth(client):
    response = client.get("/api/attention")
    assert response.status_code in (401, 302)
