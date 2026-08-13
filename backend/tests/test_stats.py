from datetime import date

import pytest

from app.extensions import db
from app.models import Event, EventStatus, EventType, TenureAward
from app.services.employees import create_person_with_employment
from app.services.events import create_manual_event
from app.services.statistics import build_dashboard_stats


def test_dashboard_stats_empty_company(seed_company, monkeypatch):
    monkeypatch.setattr("app.services.statistics.today_moscow", lambda: date(2026, 7, 24))

    stats = build_dashboard_stats(seed_company.id)

    assert stats["employees"]["active"] == 0
    assert stats["events"]["planned"] == 0
    assert stats["contracts"]["active"] == 0
    assert stats["passports"]["missing"] == 0


def test_dashboard_stats_company_isolation(seed_company, monkeypatch):
    from app.models import Company

    monkeypatch.setattr("app.services.statistics.today_moscow", lambda: date(2026, 7, 24))

    other = Company(name="Other Co")
    db.session.add(other)
    db.session.commit()

    person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Иван Иванов",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    create_manual_event(
        company_id=seed_company.id,
        title="Manual event",
        event_type=EventType.MANUAL,
        event_date=date(2026, 7, 10),
        employment_id=employment.id,
    )
    db.session.commit()

    stats = build_dashboard_stats(seed_company.id, date(2026, 1, 1), date(2026, 12, 31))
    other_stats = build_dashboard_stats(other.id, date(2026, 1, 1), date(2026, 12, 31))

    assert stats["employees"]["active"] == 1
    assert stats["events"]["overdue"] == 1
    assert other_stats["employees"]["active"] == 0
    assert other_stats["events"]["planned"] == 0


def test_dashboard_stats_period_filter(seed_company, monkeypatch):
    monkeypatch.setattr("app.services.statistics.today_moscow", lambda: date(2026, 7, 24))

    create_manual_event(
        company_id=seed_company.id,
        title="Inside period",
        event_type=EventType.MANUAL,
        event_date=date(2026, 6, 1),
    )
    create_manual_event(
        company_id=seed_company.id,
        title="Outside period",
        event_type=EventType.MANUAL,
        event_date=date(2025, 1, 1),
    )
    db.session.commit()

    stats = build_dashboard_stats(seed_company.id, date(2026, 1, 1), date(2026, 12, 31))

    assert stats["events"]["overdue"] == 1


def test_dashboard_stats_tenure_and_grades_per_company(seed_company, monkeypatch):
    monkeypatch.setattr("app.services.statistics.today_moscow", lambda: date(2026, 7, 24))

    person, employment = create_person_with_employment(
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
            is_received=True,
            received_date=date(2026, 6, 1),
        )
    )
    db.session.commit()

    stats = build_dashboard_stats(seed_company.id, date(2026, 1, 1), date(2026, 12, 31))

    assert stats["tenure"]["received"]["10"] == 1
    assert stats["tenure"]["received_in_period"] == 1


def test_stats_api_requires_auth(client):
    response = client.get("/api/stats")
    assert response.status_code in (401, 302)


def test_stats_api_viewer_can_read(viewer_client, seed_company):
    response = viewer_client.get(f"/api/stats?company_id={seed_company.id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "employees" in payload["data"]


def test_stats_api_accepts_period(admin_client, seed_company):
    response = admin_client.get(
        f"/api/stats?company_id={seed_company.id}&from=2026-01-01&to=2026-12-31"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["period"]["from"] == "2026-01-01"
