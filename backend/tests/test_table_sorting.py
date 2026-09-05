"""Sorting coverage for server-side tables."""

from datetime import date

from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    Event,
    EventSource,
    EventStatus,
    EventType,
    GradeCatalog,
    Passport,
    Reward,
    User,
)
from app.services.employees import create_person_with_employment, sync_active_contract
from app.services.events import create_manual_event, transition_event_status


def _seed_grades():
    junior = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=True)
    senior = GradeCatalog(name="Senior", rank=2, min_years=2, is_active=True)
    db.session.add_all([junior, senior])
    db.session.flush()
    return junior, senior


def test_employees_sort_by_contract_end(admin_client, seed_company):
    with admin_client.application.app_context():
        _seed_grades()
        _, early = create_person_with_employment(
            seed_company.id,
            "Раньше Конец",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        _, later = create_person_with_employment(
            seed_company.id,
            "Позже Конец",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        sync_active_contract(early, date(2026, 1, 1), term_years=1)
        sync_active_contract(later, date(2027, 1, 1), term_years=1)
        db.session.commit()

    response = admin_client.get("/api/employees?sort=contract_end&direction=asc")
    assert response.status_code == 200
    names = [item["full_name"] for item in response.get_json()["data"]["items"][:2]]
    assert names == ["Раньше Конец", "Позже Конец"]


def test_contracts_sort_by_days_left(admin_client, seed_company):
    with admin_client.application.app_context():
        _, first = create_person_with_employment(
            seed_company.id,
            "Контракт Раньше",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        _, second = create_person_with_employment(
            seed_company.id,
            "Контракт Позже",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        sync_active_contract(first, date(2026, 6, 1), term_years=1)
        sync_active_contract(second, date(2027, 6, 1), term_years=1)
        db.session.commit()

    response = admin_client.get("/api/contracts?sort=days_left&direction=asc")
    assert response.status_code == 200
    names = [item["full_name"] for item in response.get_json()["data"]["items"][:2]]
    assert names == ["Контракт Раньше", "Контракт Позже"]


def test_passports_sort_by_days_left(admin_client, seed_company):
    with admin_client.application.app_context():
        person_a, employment_a = create_person_with_employment(
            seed_company.id,
            "Паспорт Раньше",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        person_b, _ = create_person_with_employment(
            seed_company.id,
            "Паспорт Позже",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        db.session.add_all(
            [
                Passport(person_id=person_a.id, valid_until=date(2026, 1, 1), is_active=True),
                Passport(person_id=person_b.id, valid_until=date(2028, 1, 1), is_active=True),
            ]
        )
        db.session.commit()

    response = admin_client.get("/api/passports?sort=days_left&direction=asc")
    assert response.status_code == 200
    names = [item["full_name"] for item in response.get_json()["data"]["items"][:2]]
    assert names == ["Паспорт Раньше", "Паспорт Позже"]


def test_events_sort_by_source(admin_client, seed_company):
    with admin_client.application.app_context():
        _, employment = create_person_with_employment(
            seed_company.id,
            "Событие Сотрудник",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        db.session.add_all(
            [
                Event(
                    company_id=seed_company.id,
                    employment_id=employment.id,
                    title="Импорт",
                    event_type=EventType.MANUAL.value,
                    event_date=date(2026, 1, 1),
                    source=EventSource.IMPORT.value,
                ),
                Event(
                    company_id=seed_company.id,
                    employment_id=employment.id,
                    title="Ручное",
                    event_type=EventType.MANUAL.value,
                    event_date=date(2026, 2, 1),
                    source=EventSource.MANUAL.value,
                ),
            ]
        )
        db.session.commit()

    response = admin_client.get("/api/events?sort=source&direction=asc")
    assert response.status_code == 200
    titles = [item["title"] for item in response.get_json()["data"]["items"][:2]]
    assert titles == ["Импорт", "Ручное"]


def test_rewards_sort_by_notes(admin_client, seed_company):
    with admin_client.application.app_context():
        _, employment = create_person_with_employment(
            seed_company.id,
            "Поощрение Сотрудник",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        db.session.add_all(
            [
                Reward(
                    employment_id=employment.id,
                    reward_type="A",
                    status="not_delivered",
                    notes="alpha",
                ),
                Reward(
                    employment_id=employment.id,
                    reward_type="B",
                    status="not_delivered",
                    notes="beta",
                ),
            ]
        )
        db.session.commit()

    response = admin_client.get("/api/rewards?sort=notes&direction=asc")
    assert response.status_code == 200
    notes = [item["notes"] for item in response.get_json()["data"]["items"][:2]]
    assert notes == ["alpha", "beta"]


def test_events_sort_by_nearest_date(admin_client, seed_company):
    with admin_client.application.app_context():
        _, employment = create_person_with_employment(
            seed_company.id,
            "Событие Сотрудник",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
        )
        db.session.add_all(
            [
                Event(
                    company_id=seed_company.id,
                    employment_id=employment.id,
                    title="Прошлое",
                    event_type=EventType.MANUAL.value,
                    event_date=date(2020, 1, 1),
                    source=EventSource.MANUAL.value,
                ),
                Event(
                    company_id=seed_company.id,
                    employment_id=employment.id,
                    title="Будущее ближе",
                    event_type=EventType.MANUAL.value,
                    event_date=date(2030, 1, 1),
                    source=EventSource.MANUAL.value,
                ),
                Event(
                    company_id=seed_company.id,
                    employment_id=employment.id,
                    title="Будущее дальше",
                    event_type=EventType.MANUAL.value,
                    event_date=date(2035, 1, 1),
                    source=EventSource.MANUAL.value,
                ),
            ]
        )
        db.session.commit()

    response = admin_client.get("/api/events?sort=nearest_date&direction=asc")
    assert response.status_code == 200
    titles = [item["title"] for item in response.get_json()["data"]["items"]]
    assert titles[:3] == ["Будущее ближе", "Будущее дальше", "Прошлое"]


def test_events_sort_by_planned_nearest(admin_client, seed_company, monkeypatch):
    monkeypatch.setattr("app.services.events.today_moscow", lambda: date(2026, 6, 1))

    with admin_client.application.app_context():
        planned_far = create_manual_event(
            company_id=seed_company.id,
            title="План дальше",
            event_type=EventType.MANUAL,
            event_date=date(2026, 12, 1),
        )
        planned_near = create_manual_event(
            company_id=seed_company.id,
            title="План ближе",
            event_type=EventType.MANUAL,
            event_date=date(2026, 7, 1),
        )
        overdue = create_manual_event(
            company_id=seed_company.id,
            title="Просрочено",
            event_type=EventType.MANUAL,
            event_date=date(2026, 1, 1),
        )
        completed = create_manual_event(
            company_id=seed_company.id,
            title="Выполнено",
            event_type=EventType.MANUAL,
            event_date=date(2026, 5, 1),
        )
        transition_event_status(completed, EventStatus.COMPLETED, "done")
        db.session.commit()

    response = admin_client.get("/api/events?sort=planned_nearest&direction=asc")
    assert response.status_code == 200
    titles = [item["title"] for item in response.get_json()["data"]["items"]]
    assert titles.index("План ближе") < titles.index("План дальше")
    assert titles.index("План дальше") < titles.index("Просрочено")
    assert titles.index("Просрочено") < titles.index("Выполнено")


def test_events_sort_keeps_cancelled_last(admin_client, seed_company):
    with admin_client.application.app_context():
        early = create_manual_event(
            company_id=seed_company.id,
            title="А раннее",
            event_type=EventType.MANUAL,
            event_date=date(2026, 1, 1),
        )
        late = create_manual_event(
            company_id=seed_company.id,
            title="Я позднее",
            event_type=EventType.MANUAL,
            event_date=date(2026, 6, 1),
        )
        cancelled = create_manual_event(
            company_id=seed_company.id,
            title="Б отменено",
            event_type=EventType.MANUAL,
            event_date=date(2026, 3, 1),
        )
        transition_event_status(cancelled, EventStatus.CANCELLED, "не нужно")
        db.session.commit()
        early_id, late_id, cancelled_id = early.id, late.id, cancelled.id

    by_title = admin_client.get("/api/events?sort=title&direction=asc")
    assert by_title.status_code == 200
    title_ids = [item["id"] for item in by_title.get_json()["data"]["items"]]
    assert title_ids.index(early_id) < title_ids.index(late_id)
    assert title_ids[-1] == cancelled_id

    by_date = admin_client.get("/api/events?sort=event_date&direction=desc")
    assert by_date.status_code == 200
    date_ids = [item["id"] for item in by_date.get_json()["data"]["items"]]
    assert date_ids.index(late_id) < date_ids.index(early_id)
    assert date_ids[-1] == cancelled_id


def test_grades_sort_by_eligible_date_nearest(admin_client, seed_company):
    from app.models import GradeCatalog
    from app.services.grades import assign_grade_to_employment

    with admin_client.application.app_context():
        junior = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=True)
        senior = GradeCatalog(name="Senior", rank=2, min_years=2, is_active=True)
        db.session.add_all([junior, senior])
        db.session.flush()

        _, available_employment = create_person_with_employment(
            seed_company.id,
            "Доступный",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
            position_grade_id=senior.id,
        )
        _, future_employment = create_person_with_employment(
            seed_company.id,
            "Будущий",
            date(2020, 1, 1),
            "Инженер",
            education_status="yes",
            position_grade_id=senior.id,
        )
        assign_grade_to_employment(available_employment, junior, date(2020, 1, 1))
        assign_grade_to_employment(future_employment, junior, date(2026, 6, 1))
        db.session.commit()

    response = admin_client.get("/api/grades?sort=eligible_date_nearest&direction=asc")
    assert response.status_code == 200
    names = [item["full_name"] for item in response.get_json()["data"]["items"]]
    assert names[0] == "Доступный"
    assert names.index("Будущий") > names.index("Доступный")


def test_tenure_sort_by_continuous_tenure_years(admin_client, seed_company):
    with admin_client.application.app_context():
        create_person_with_employment(
            seed_company.id,
            "Новый Стаж",
            date(2022, 1, 1),
            "Инженер",
            education_status="yes",
        )
        create_person_with_employment(
            seed_company.id,
            "Длинный Стаж",
            date(2010, 1, 1),
            "Инженер",
            education_status="yes",
        )
        db.session.commit()

    response = admin_client.get("/api/tenure?sort=continuous_tenure_years&direction=desc")
    assert response.status_code == 200
    names = [item["full_name"] for item in response.get_json()["data"]["items"][:2]]
    assert names == ["Длинный Стаж", "Новый Стаж"]
