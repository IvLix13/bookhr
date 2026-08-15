from datetime import date

from app.extensions import db
from app.models import (
    Event,
    EventStatus,
    EventType,
    GradeCatalog,
    Employment,
)
from app.services.employees import create_person_with_employment


def _seed_grades() -> None:
    db.session.add_all(
        [
            GradeCatalog(name="Мидл", rank=3, min_years=1.5),
            GradeCatalog(name="Сеньор", rank=4, min_years=2),
        ]
    )
    db.session.commit()


def test_create_employee_creates_rule_events(hr_client, seed_company):
    with hr_client.application.app_context():
        _seed_grades()
        middle_id = GradeCatalog.query.filter_by(name="Мидл").first().id
        senior_id = GradeCatalog.query.filter_by(name="Сеньор").first().id

    response = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Новиков Иван Иванович",
            "title": "Инженер",
            "hire_date": "2021-01-10",
            "has_university": True,
            "position_grade_id": senior_id,
            "actual_grade_id": middle_id,
            "grade_date": "2024-03-01",
            "contract_end": "2026-12-01",
            "passport_until": "2029-08-20",
        },
    )
    assert response.status_code == 201
    employment_id = response.get_json()["data"]["id"]

    with hr_client.application.app_context():
        events = Event.query.filter_by(
            employment_id=employment_id,
            source="rule",
        ).all()
        types = {event.event_type for event in events}
        assert types == {
            EventType.REPORT.value,
            EventType.GRADE.value,
            EventType.PASSPORT.value,
        }


def test_update_contract_end_recalculates_events(hr_client, seed_company):
    with hr_client.application.app_context():
        _seed_grades()
        middle_id = GradeCatalog.query.filter_by(name="Мидл").first().id

    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Петров Пётр Петрович",
            "title": "Аналитик",
            "hire_date": "2020-05-01",
            "actual_grade_id": middle_id,
            "grade_date": "2023-01-01",
            "contract_end": "2026-12-01",
            "passport_until": "2030-01-01",
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]

    with hr_client.application.app_context():
        old_report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
        ).one()
        old_id = old_report.id
        old_date = old_report.event_date

    updated = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"contract_end": "2027-06-01"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["contract_end"] == "2027-06-01"

    with hr_client.application.app_context():
        old_report = db.session.get(Event, old_id)
        assert old_report is not None
        assert old_report.status == EventStatus.CANCELLED.value

        new_report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
            status=EventStatus.PLANNED.value,
        ).one()
        assert new_report.event_date != old_date
        assert new_report.event_date == date(2027, 2, 1)


def test_update_name_updates_event_titles(hr_client, seed_company):
    with hr_client.application.app_context():
        _seed_grades()

    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Сидоров Сидор Сидорович",
            "title": "Инженер",
            "hire_date": "2022-01-01",
            "contract_end": "2026-12-01",
            "passport_until": "2028-01-01",
        },
    )
    employment_id = created.get_json()["data"]["id"]

    response = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"full_name": "Сидоров Алексей Сидорович"},
    )
    assert response.status_code == 200

    with hr_client.application.app_context():
        events = Event.query.filter_by(
            employment_id=employment_id,
            source="rule",
        ).all()
        assert events
        assert all("Сидоров Алексей Сидорович" in event.title for event in events)


def test_delete_employee_removes_events(hr_client, seed_company):
    with hr_client.application.app_context():
        _seed_grades()

    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Удаляев Удал Удалович",
            "title": "Инженер",
            "hire_date": "2021-01-01",
            "contract_end": "2026-12-01",
            "passport_until": "2029-01-01",
        },
    )
    employment_id = created.get_json()["data"]["id"]

    deleted = hr_client.delete(f"/api/employees/{employment_id}")
    assert deleted.status_code == 200

    with hr_client.application.app_context():
        assert db.session.get(Employment, employment_id) is None
        assert Event.query.filter_by(employment_id=employment_id).count() == 0


def test_viewer_cannot_mutate_employees(viewer_client, seed_company):
    with viewer_client.application.app_context():
        person, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Наблюдатель Тест",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.commit()
        employment_id = employment.id

    assert viewer_client.post(
        "/api/employees",
        json={
            "full_name": "X",
            "hire_date": "2020-01-01",
        },
    ).status_code == 403
    assert viewer_client.patch(
        f"/api/employees/{employment_id}",
        json={"full_name": "Y"},
    ).status_code == 403
    assert viewer_client.delete(f"/api/employees/{employment_id}").status_code == 403


def test_create_employee_with_contract_term_years(hr_client, seed_company):
    response = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Контрактов Срок Срокович",
            "title": "Менеджер",
            "hire_date": "2024-09-01",
            "contract_term_years": 2,
        },
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["contract_term_years"] == 2
    assert data["contract_end"] == "2026-09-01"

    employment_id = data["id"]
    with hr_client.application.app_context():
        report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
        ).one()
        assert report.event_date == date(2026, 5, 1)

    updated = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"contract_term_years": 3},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["contract_term_years"] == 3
    assert updated.get_json()["data"]["contract_end"] == "2027-09-01"

    manual_end = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"contract_end": "2029-09-01"},
    )
    assert manual_end.status_code == 200
    assert manual_end.get_json()["data"]["contract_term_years"] == 5.0
    assert manual_end.get_json()["data"]["contract_end"] == "2029-09-01"

    with hr_client.application.app_context():
        report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
            status=EventStatus.PLANNED.value,
        ).one()
        assert report.event_date == date(2029, 5, 1)


def test_create_employee_invalid_contract_end_rejected(hr_client, seed_company):
    response = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Невалидов Дата",
            "hire_date": "2024-09-01",
            "contract_end": "2024-08-01",
        },
    )
    assert response.status_code == 400


def test_update_contract_directly(hr_client, seed_company):
    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Прямов Контракт",
            "hire_date": "2024-01-01",
            "contract_end": "2025-01-01",
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]

    contracts = hr_client.get(f"/api/contracts?company_id={seed_company.id}").get_json()["data"]["items"]
    contract_item = next(c for c in contracts if c["employment_id"] == employment_id)
    contract_id = contract_item["id"]
    assert contract_item["term_years"] == 1.0

    updated = hr_client.patch(
        f"/api/contracts/{contract_id}",
        json={"end_date": "2027-01-01"},
    )
    assert updated.status_code == 200
    data = updated.get_json()["data"]
    assert data["end_date"] == "2027-01-01"
    assert data["term_years"] == 3.0

    invalid = hr_client.patch(
        f"/api/contracts/{contract_id}",
        json={"end_date": "2023-01-01"},
    )
    assert invalid.status_code == 400


