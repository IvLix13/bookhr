"""Integration tests: tenure award events appear in API and UI feeds."""

from datetime import date

from app.extensions import db
from app.models import Event, EventStatus, EventType, TenureAward
from app.services.employees import create_person_with_employment
from app.services.rule_engine import run_rule_engine, tenure_award_event_date
from app.services.tenure import ensure_tenure_awards


def test_tenure_award_event_date_uses_today_when_milestone_past(monkeypatch):
    monkeypatch.setattr("app.services.rule_engine.today_moscow", lambda: date(2026, 7, 24))
    assert tenure_award_event_date(date(2010, 1, 1)) == date(2026, 7, 24)
    assert tenure_award_event_date(date(2027, 1, 1)) == date(2027, 1, 1)


def test_run_rules_creates_award_events_visible_in_api(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.services.rule_engine.today_moscow", lambda: date(2026, 7, 24))

    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="API Награда",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    db.session.commit()

    with admin_client.application.app_context():
        stats = run_rule_engine(seed_company.id)
        db.session.commit()
        assert stats["tenure"] >= 1

    list_response = admin_client.get(f"/api/events?company_id={seed_company.id}&per_page=50")
    assert list_response.status_code == 200
    items = list_response.get_json()["data"]["items"]
    award_events = [item for item in items if item["event_type"] == EventType.AWARD.value]
    assert award_events
    assert award_events[0]["event_date"] == "2026-07-24"
    assert "10 лет" in award_events[0]["title"]

    upcoming_response = admin_client.get(f"/api/events/upcoming?company_id={seed_company.id}&limit=20")
    assert upcoming_response.status_code == 200
    upcoming = upcoming_response.get_json()["data"]
    assert any(item["event_type"] == EventType.AWARD.value for item in upcoming)

    month_response = admin_client.get(
        f"/api/events?company_id={seed_company.id}"
        f"&from=2026-07-01&to=2026-07-31&per_page=50"
    )
    assert month_response.status_code == 200
    month_items = month_response.get_json()["data"]["items"]
    assert any(item["event_type"] == EventType.AWARD.value for item in month_items)


def test_complete_award_event_marks_tenure_received(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.services.rule_engine.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.services.event_completion.today_moscow", lambda: date(2026, 7, 24))

    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Завершение Награда",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    awards = ensure_tenure_awards(employment.person_id, employment.company_id)
    db.session.commit()
    award = next(a for a in awards if a.milestone_years == 10)

    with admin_client.application.app_context():
        run_rule_engine(seed_company.id)
        db.session.commit()
        event = Event.query.filter_by(
            employment_id=employment.id,
            event_type=EventType.AWARD.value,
        ).first()
        event_id = event.id

    complete = admin_client.post(f"/api/events/{event_id}/complete", json={})
    assert complete.status_code == 200
    assert complete.get_json()["data"]["status"] == EventStatus.COMPLETED.value

    with admin_client.application.app_context():
        award = db.session.get(TenureAward, award.id)
        assert award is not None
        assert award.is_received is True
        assert award.received_date == date(2020, 1, 1)


def test_no_award_event_when_lower_milestone_missing(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 7, 24))
    monkeypatch.setattr("app.services.rule_engine.today_moscow", lambda: date(2026, 7, 24))

    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Без Десятилетки API",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    db.session.add(
        TenureAward(
            person_id=employment.person_id,
            company_id=employment.company_id,
            milestone_years=15,
            milestone_date=date(2020, 1, 1),
            is_received=False,
        )
    )
    db.session.commit()

    with admin_client.application.app_context():
        stats = run_rule_engine(seed_company.id)
        db.session.commit()
        assert stats["tenure"] >= 1

    list_response = admin_client.get(f"/api/events?company_id={seed_company.id}&type=award")
    assert list_response.status_code == 200
    items = list_response.get_json()["data"]["items"]
    assert not any("15 лет" in item["title"] for item in items)
