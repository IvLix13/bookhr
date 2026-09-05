from datetime import date

from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
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
            "education_status": "yes",
            "position_grade_id": senior_id,
            "actual_grade_id": middle_id,
            "grade_date": "2024-03-01",
            "contract_term_years": 1,
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


def test_create_employee_requires_explicit_education_status(hr_client, seed_company):
    missing = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Без Статуса",
            "hire_date": "2024-01-01",
        },
    )
    unknown = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Неизвестный Статус",
            "hire_date": "2024-01-01",
            "education_status": "unknown",
        },
    )
    assert missing.status_code == 400
    assert unknown.status_code == 400


def test_resolving_unknown_education_initializes_current_rank_policy(
    hr_client,
    seed_company,
):
    with hr_client.application.app_context():
        junior = GradeCatalog(
            name="Джун",
            rank=1,
            min_years=1,
            extra_year_without_university=True,
        )
        middle = GradeCatalog(name="Мидл", rank=2, min_years=1)
        db.session.add_all([junior, middle])
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Уточняемый Сотрудник",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
        )
        history = EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=junior.id,
            assigned_date=date(2024, 1, 1),
        )
        db.session.add(history)
        db.session.commit()
        employment_id = employment.id

    response = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"education_status": "yes"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["eligible_date"] == "2025-01-01"

    with hr_client.application.app_context():
        history = EmployeeGradeHistory.query.filter_by(
            employment_id=employment_id,
            valid_to=None,
        ).one()
        assert history.education_status_at_rank_entry == "yes"
        assert history.required_months == 12
        assert Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.GRADE.value,
        ).count() == 2


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
            "education_status": "no",
            "actual_grade_id": middle_id,
            "grade_date": "2023-01-01",
            "contract_term_years": 1,
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
        json={"contract_term_years": 2, "contract_end": "2027-06-01"},
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
            "education_status": "no",
            "contract_term_years": 1,
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
            "education_status": "no",
            "contract_term_years": 1,
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


def test_create_employee_with_contract_fields(hr_client, seed_company):
    response = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Контрактов Срок Срокович",
            "title": "Менеджер",
            "hire_date": "2020-01-01",
            "education_status": "no",
            "contract_term_years": 2,
            "contract_end": "2027-06-01",
        },
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["contract_term_years"] == 2
    assert data["contract_end"] == "2027-06-01"

    employment_id = data["id"]
    with hr_client.application.app_context():
        contract = Contract.query.join(Employment).filter(Employment.id == employment_id).one()
        assert contract.start_date == date(2025, 6, 1)
        report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
        ).one()
        assert report.event_date == date(2027, 2, 1)

    updated = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"contract_term_years": 3, "contract_end": "2028-06-01"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["contract_term_years"] == 3
    assert updated.get_json()["data"]["contract_end"] == "2028-06-01"

    manual_end = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"contract_term_years": 5, "contract_end": "2030-06-01"},
    )
    assert manual_end.status_code == 200
    assert manual_end.get_json()["data"]["contract_term_years"] == 5
    assert manual_end.get_json()["data"]["contract_end"] == "2030-06-01"

    with hr_client.application.app_context():
        report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
            status=EventStatus.PLANNED.value,
        ).one()
        assert report.event_date == date(2030, 2, 1)


def test_create_employee_rejects_partial_contract_fields(hr_client, seed_company):
    only_end = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Невалидов Дата",
            "hire_date": "2024-09-01",
            "education_status": "no",
            "contract_end": "2026-08-01",
        },
    )
    assert only_end.status_code == 400

    only_term = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Невалидов Срок",
            "hire_date": "2024-09-01",
            "education_status": "no",
            "contract_term_years": 2,
        },
    )
    assert only_term.status_code == 400


def test_update_contract_directly(hr_client, seed_company):
    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Прямов Контракт",
            "hire_date": "2024-01-01",
            "education_status": "no",
            "contract_term_years": 1,
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
        json={"end_date": "2027-01-01", "term_years": 3},
    )
    assert updated.status_code == 200
    data = updated.get_json()["data"]
    assert data["end_date"] == "2027-01-01"
    assert data["term_years"] == 3.0
    assert data["start_date"] == "2024-01-01"

    invalid = hr_client.patch(
        f"/api/contracts/{contract_id}",
        json={"end_date": "2027-01-01"},
    )
    assert invalid.status_code == 400


def test_update_contract_directly_recalculates_renewal_report(hr_client, seed_company):
    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Рапортов Контракт",
            "hire_date": "2020-05-01",
            "education_status": "no",
            "contract_term_years": 1,
            "contract_end": "2026-12-01",
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]

    contracts = hr_client.get(f"/api/contracts?company_id={seed_company.id}").get_json()["data"]["items"]
    contract_item = next(c for c in contracts if c["employment_id"] == employment_id)
    contract_id = contract_item["id"]
    assert contract_item["start_date"] == "2025-12-01"
    assert contract_item["renewal_report_event"]["event_date"] == "2026-08-01"

    with hr_client.application.app_context():
        old_report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
        ).one()
        old_id = old_report.id

    updated = hr_client.patch(
        f"/api/contracts/{contract_id}",
        json={"end_date": "2027-06-01", "term_years": 2},
    )
    assert updated.status_code == 200
    data = updated.get_json()["data"]
    assert data["end_date"] == "2027-06-01"
    assert data["term_years"] == 2.0
    assert data["start_date"] == "2025-06-01"
    assert data["renewal_report_event"]["event_date"] == "2027-02-01"

    with hr_client.application.app_context():
        old_report = db.session.get(Event, old_id)
        assert old_report is not None
        assert old_report.status == EventStatus.CANCELLED.value

        new_report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
            status=EventStatus.PLANNED.value,
        ).one()
        assert new_report.event_date == date(2027, 2, 1)


def test_update_contract_report_date_is_kept_after_recalculation(hr_client, seed_company):
    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Рапорт Дата",
            "hire_date": "2020-05-01",
            "education_status": "no",
            "contract_term_years": 1,
            "contract_end": "2026-12-01",
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]

    contracts = hr_client.get(f"/api/contracts?company_id={seed_company.id}").get_json()["data"]["items"]
    contract_item = next(c for c in contracts if c["employment_id"] == employment_id)
    contract_id = contract_item["id"]
    assert contract_item["renewal_report_event"]["event_date"] == "2026-08-01"
    report_id = contract_item["renewal_report_event"]["id"]

    updated = hr_client.patch(
        f"/api/contracts/{contract_id}",
        json={"report_date": "2026-05-15"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["renewal_report_event"]["event_date"] == "2026-05-15"

    renamed = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"full_name": "Рапорт Дата Новая"},
    )
    assert renamed.status_code == 200

    contracts = hr_client.get(f"/api/contracts?company_id={seed_company.id}").get_json()["data"]["items"]
    contract_item = next(c for c in contracts if c["employment_id"] == employment_id)
    assert contract_item["renewal_report_event"]["id"] == report_id
    assert contract_item["renewal_report_event"]["event_date"] == "2026-05-15"

    with hr_client.application.app_context():
        report = db.session.get(Event, report_id)
        assert report is not None
        assert report.manual_date is True
        assert report.event_date == date(2026, 5, 15)


def test_update_contract_report_date_back_to_default_unlocks_recalc(hr_client, seed_company):
    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Рапорт Сброс",
            "hire_date": "2020-05-01",
            "education_status": "no",
            "contract_term_years": 2,
            "contract_end": "2027-06-01",
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]
    contracts = hr_client.get(f"/api/contracts?company_id={seed_company.id}").get_json()["data"]["items"]
    contract_id = next(c["id"] for c in contracts if c["employment_id"] == employment_id)

    hr_client.patch(f"/api/contracts/{contract_id}", json={"report_date": "2027-01-01"})
    restored = hr_client.patch(
        f"/api/contracts/{contract_id}",
        json={"report_date": "2027-02-01"},
    )
    assert restored.status_code == 200
    data = restored.get_json()["data"]
    assert data["renewal_report_event"]["event_date"] == "2027-02-01"

    with hr_client.application.app_context():
        report = Event.query.filter_by(
            employment_id=employment_id,
            event_type=EventType.REPORT.value,
            status=EventStatus.PLANNED.value,
        ).one()
        assert report.manual_date is False


def test_update_contract_report_date_reopens_cancelled_report(hr_client, seed_company):
    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Рапорт Отмена",
            "hire_date": "2020-05-01",
            "education_status": "no",
            "contract_term_years": 1,
            "contract_end": "2026-12-01",
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]
    contracts = hr_client.get(f"/api/contracts?company_id={seed_company.id}").get_json()["data"]["items"]
    contract_item = next(c for c in contracts if c["employment_id"] == employment_id)
    contract_id = contract_item["id"]
    report_id = contract_item["renewal_report_event"]["id"]

    cancelled = hr_client.post(f"/api/events/{report_id}/cancel", json={"comment": "Не нужен"})
    assert cancelled.status_code == 200

    listed = hr_client.get(f"/api/contracts?company_id={seed_company.id}").get_json()["data"]["items"]
    hidden = next(c for c in listed if c["employment_id"] == employment_id)
    assert hidden["renewal_report_event"] is None

    updated = hr_client.patch(
        f"/api/contracts/{contract_id}",
        json={"report_date": "2026-11-10", "end_date": "2026-12-01", "term_years": 1},
    )
    assert updated.status_code == 200
    report = updated.get_json()["data"]["renewal_report_event"]
    assert report is not None
    assert report["id"] == report_id
    assert report["event_date"] == "2026-11-10"
    assert report["status"] == EventStatus.PLANNED.value


def test_viewer_cannot_update_contract(viewer_client, seed_company):
    with viewer_client.application.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Зрителев Договор",
            hire_date=date(2024, 1, 1),
            title="Инженер",
        )
        contract = Contract(
            employment_id=employment.id,
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
            term_years=1,
            is_active=True,
        )
        db.session.add(contract)
        db.session.commit()
        contract_id = contract.id

    response = viewer_client.patch(
        f"/api/contracts/{contract_id}",
        json={"end_date": "2027-01-01", "term_years": 3},
    )
    assert response.status_code == 403


