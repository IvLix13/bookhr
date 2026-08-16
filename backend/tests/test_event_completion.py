from datetime import date

from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    Event,
    EventStatus,
    EventType,
    GradeCatalog,
)
from app.services.employees import create_person_with_employment, get_current_grade
from app.services.events import create_manual_event
from app.services.rule_engine import process_contract_rules


def _grade_pair() -> tuple[GradeCatalog, GradeCatalog]:
    junior = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=True)
    middle = GradeCatalog(name="Middle", rank=2, min_years=2, is_active=True)
    db.session.add_all([junior, middle])
    db.session.flush()
    return junior, middle


def test_completing_grade_event_promotes_employee(hr_client, seed_company, app):
    with app.app_context():
        junior, middle = _grade_pair()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд Растёт",
            hire_date=date(2018, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
            education_status="yes",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=junior.id,
                assigned_date=date(2020, 1, 1),
            )
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Рассмотреть повышение грейда",
            event_type=EventType.GRADE,
            event_date=date(2021, 1, 1),
            employment_id=employment.id,
        )
        db.session.commit()
        event_id = event.id
        employment_id = employment.id
        middle_id = middle.id

    response = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert response.status_code == 200

    with app.app_context():
        employment = db.session.get(Employment, employment_id)
        current = get_current_grade(employment)
        assert current is not None
        assert current.grade_id == middle_id


def test_completing_grade_event_without_next_grade_keeps_grade(hr_client, seed_company, app):
    """At the grade required by the position there is nothing to promote to."""
    with app.app_context():
        _junior, middle = _grade_pair()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд На Пике",
            hire_date=date(2018, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
            education_status="yes",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=middle.id,
                assigned_date=date(2020, 1, 1),
            )
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Рассмотреть повышение грейда",
            event_type=EventType.GRADE,
            event_date=date(2021, 1, 1),
            employment_id=employment.id,
        )
        db.session.commit()
        event_id = event.id
        employment_id = employment.id
        middle_id = middle.id

    response = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert response.status_code == 200

    with app.app_context():
        employment = db.session.get(Employment, employment_id)
        current = get_current_grade(employment)
        assert current is not None
        assert current.grade_id == middle_id
        assert EmployeeGradeHistory.query.filter_by(employment_id=employment_id).count() == 1


def test_completing_grade_event_starts_no_earlier_than_eligible_date(
    hr_client, seed_company, app
):
    with app.app_context():
        junior, middle = _grade_pair()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд Заранее",
            hire_date=date(2018, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
            education_status="yes",
        )
        # min_years=1 for Junior, so eligibility starts far in the future.
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=junior.id,
                assigned_date=date(2099, 1, 1),
            )
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Рассмотреть повышение грейда",
            event_type=EventType.GRADE,
            event_date=date(2099, 12, 1),
            employment_id=employment.id,
        )
        db.session.commit()
        event_id = event.id
        employment_id = employment.id

    response = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert response.status_code == 200

    with app.app_context():
        employment = db.session.get(Employment, employment_id)
        current = get_current_grade(employment)
        assert current is not None
        assert current.assigned_date == date(2100, 1, 1)


def test_reopened_grade_event_does_not_promote_twice(hr_client, seed_company, app):
    with app.app_context():
        junior, middle = _grade_pair()
        senior = GradeCatalog(name="Senior", rank=3, min_years=3, is_active=True)
        db.session.add(senior)
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд Дважды",
            hire_date=date(2010, 1, 1),
            title="Инженер",
            position_grade_id=senior.id,
            education_status="yes",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=junior.id,
                assigned_date=date(2012, 1, 1),
            )
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Рассмотреть повышение грейда",
            event_type=EventType.GRADE,
            event_date=date(2013, 1, 1),
            employment_id=employment.id,
        )
        db.session.commit()
        event_id = event.id
        employment_id = employment.id
        middle_id = middle.id

    assert hr_client.post(f"/api/events/{event_id}/complete", json={}).status_code == 200
    assert hr_client.post(f"/api/events/{event_id}/reopen", json={}).status_code == 200
    assert hr_client.post(f"/api/events/{event_id}/complete", json={}).status_code == 200

    with app.app_context():
        employment = db.session.get(Employment, employment_id)
        current = get_current_grade(employment)
        assert current is not None
        assert current.grade_id == middle_id
        assert EmployeeGradeHistory.query.filter_by(employment_id=employment_id).count() == 2


def test_multiple_next_grades_require_hr_selection(hr_client, seed_company, app):
    with app.app_context():
        junior = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=True)
        middle_a = GradeCatalog(name="Middle A", rank=2, min_years=1, is_active=True)
        middle_b = GradeCatalog(name="Middle B", rank=2, min_years=1, is_active=True)
        db.session.add_all([junior, middle_a, middle_b])
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Выбор Грейда",
            hire_date=date(2018, 1, 1),
            title="Инженер",
            position_grade_id=middle_a.id,
            education_status="yes",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=junior.id,
                assigned_date=date(2020, 1, 1),
            )
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Рассмотреть повышение грейда",
            event_type=EventType.GRADE,
            event_date=date(2021, 1, 1),
            employment_id=employment.id,
        )
        db.session.commit()
        event_id = event.id
        employment_id = employment.id
        middle_b_id = middle_b.id

    missing = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert missing.status_code == 400
    assert missing.get_json()["message"] == "Выберите следующий грейд"

    selected = hr_client.post(
        f"/api/events/{event_id}/complete",
        json={"target_grade_id": middle_b_id},
    )
    assert selected.status_code == 200

    with app.app_context():
        event = db.session.get(Event, event_id)
        employment = db.session.get(Employment, employment_id)
        assert event.status == EventStatus.COMPLETED.value
        assert get_current_grade(employment).grade_id == middle_b_id


def test_unknown_education_blocks_grade_event_completion(
    hr_client,
    seed_company,
    app,
):
    with app.app_context():
        junior, middle = _grade_pair()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Неизвестное Образование",
            hire_date=date(2018, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=junior.id,
                assigned_date=date(2020, 1, 1),
            )
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Рассмотреть повышение грейда",
            event_type=EventType.GRADE,
            event_date=date(2021, 1, 1),
            employment_id=employment.id,
        )
        db.session.commit()
        event_id = event.id

    response = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert response.status_code == 400
    assert "образования" in response.get_json()["message"]

    with app.app_context():
        assert db.session.get(Event, event_id).status == EventStatus.PLANNED.value


def test_completing_report_event_keeps_contract_report_date(hr_client, seed_company, app):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Договор Рапорт",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            education_status="yes",
        )
        contract = Contract(
            employment_id=employment.id,
            start_date=date(2025, 1, 1),
            end_date=date(2027, 12, 1),
            is_active=True,
        )
        db.session.add(contract)
        db.session.commit()
        process_contract_rules(employment)
        db.session.commit()

        event = Event.query.filter_by(
            employment_id=employment.id,
            event_type=EventType.REPORT.value,
        ).first()
        assert event is not None
        event_id = event.id
        report_date = event.event_date.isoformat()
        contract_id = contract.id

    response = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert response.status_code == 200

    listed = hr_client.get(f"/api/contracts?company_id={seed_company.id}")
    assert listed.status_code == 200
    row = next(
        item for item in listed.get_json()["data"]["items"] if item["id"] == contract_id
    )
    report = row["renewal_report_event"]
    assert report is not None
    assert report["event_date"] == report_date
    assert report["status"] == EventStatus.COMPLETED.value
    assert report["completed_date"] is not None


def test_completing_report_event_with_extension_term_extends_contract_and_generates_next_report(
    hr_client, seed_company, app
):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Продление Договора",
            hire_date=date(2024, 9, 1),
            title="Инженер",
            education_status="yes",
        )
        contract = Contract(
            employment_id=employment.id,
            start_date=date(2024, 9, 1),
            end_date=date(2026, 9, 1),
            term_years=2,
            is_active=True,
        )
        db.session.add(contract)
        db.session.commit()
        process_contract_rules(employment)
        db.session.commit()

        event = Event.query.filter_by(
            employment_id=employment.id,
            event_type=EventType.REPORT.value,
        ).first()
        assert event is not None
        assert event.event_date == date(2026, 5, 1)
        event_id = event.id
        contract_id = contract.id

    response = hr_client.post(
        f"/api/events/{event_id}/complete",
        json={"extension_term_years": 3, "comment": "Руководство подписало продление на 3 года"},
    )
    assert response.status_code == 200

    with app.app_context():
        updated_contract = db.session.get(Contract, contract_id)
        assert updated_contract.end_date == date(2029, 9, 1)
        assert updated_contract.term_years == 3

        old_event = db.session.get(Event, event_id)
        assert old_event.status == EventStatus.COMPLETED.value
        assert old_event.completion_comment == "Руководство подписало продление на 3 года"

        new_event = Event.query.filter_by(
            employment_id=updated_contract.employment_id,
            event_type=EventType.REPORT.value,
            status=EventStatus.PLANNED.value,
        ).first()
        assert new_event is not None
        assert new_event.event_date == date(2029, 5, 1)



def test_completed_grade_event_clears_grade_attention_item(hr_client, seed_company, app):
    with app.app_context():
        junior, middle = _grade_pair()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Внимание Грейд",
            hire_date=date(2018, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
            education_status="yes",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=junior.id,
                assigned_date=date(2020, 1, 1),
            )
        )
        event = create_manual_event(
            company_id=seed_company.id,
            title="Рассмотреть повышение грейда",
            event_type=EventType.GRADE,
            event_date=date(2021, 1, 1),
            employment_id=employment.id,
        )
        db.session.commit()
        event_id = event.id

    before = hr_client.get(
        f"/api/attention?company_id={seed_company.id}&categories=grades&limit=5"
    )
    assert before.get_json()["data"]["counts"]["grades"] == 1

    complete = hr_client.post(f"/api/events/{event_id}/complete", json={})
    assert complete.status_code == 200

    after = hr_client.get(
        f"/api/attention?company_id={seed_company.id}&categories=grades&limit=5"
    )
    assert after.get_json()["data"]["counts"]["grades"] == 0


def test_attention_contract_item_carries_related_event(hr_client, seed_company, app):
    with app.app_context():
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Договор Внимание",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            education_status="yes",
        )
        contract = Contract(
            employment_id=employment.id,
            start_date=date(2020, 1, 1),
            end_date=date.today(),
            is_active=True,
        )
        db.session.add(contract)
        db.session.commit()
        process_contract_rules(employment)
        db.session.commit()
        event = Event.query.filter_by(
            employment_id=employment.id,
            event_type=EventType.REPORT.value,
        ).first()
        assert event is not None
        event_id = event.id

    response = hr_client.get(
        f"/api/attention?company_id={seed_company.id}&categories=contracts&limit=5"
    )
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert items
    assert items[0]["category"] == "contracts"
    assert items[0]["event_id"] == event_id
