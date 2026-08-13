from datetime import date

from app.extensions import db
from app.models import EmployeeGradeHistory, GradeCatalog
from app.services.employees import create_person_with_employment
from app.services.grades import compute_grade_eligibility


def test_create_grade_catalog_as_admin(admin_client, app):
    with app.app_context():
        before = GradeCatalog.query.count()

    response = admin_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 1, "min_years": 2},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["name"] == "Lead"
    assert payload["data"]["min_years"] == 2

    with app.app_context():
        assert GradeCatalog.query.count() == before + 1


def test_create_grade_catalog_requires_rank_continuity(admin_client):
    response = admin_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 3, "min_years": 2},
    )
    assert response.status_code == 400
    assert "missing prerequisite ranks" in response.get_json()["message"]


def test_create_grade_catalog_rejects_invalid_min_years(admin_client):
    response = admin_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 1, "min_years": 1.25},
    )
    assert response.status_code == 400
    assert "0.5 year steps" in response.get_json()["message"]


def test_update_grade_catalog_as_admin(admin_client, app):
    with app.app_context():
        grade = GradeCatalog(name="Junior", rank=1, min_years=1)
        db.session.add(grade)
        db.session.commit()
        grade_id = grade.id

    response = admin_client.patch(
        f"/api/grade-catalog/{grade_id}",
        json={"min_years": 1.5, "name": "Junior+"}, 
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["name"] == "Junior+"
    assert data["min_years"] == 1.5


def test_deactivate_grade_catalog_as_admin(admin_client, app):
    with app.app_context():
        grade = GradeCatalog(name="Junior", rank=1, min_years=1)
        db.session.add(grade)
        db.session.commit()
        grade_id = grade.id

    response = admin_client.patch(
        f"/api/grade-catalog/{grade_id}",
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["is_active"] is False


def test_create_grade_catalog_forbidden_for_viewer(viewer_client):
    response = viewer_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 1, "min_years": 2},
    )
    assert response.status_code == 403


def test_create_grade_catalog_as_hr(hr_client, app):
    with app.app_context():
        before = GradeCatalog.query.count()

    response = hr_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 1, "min_years": 2},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["name"] == "Lead"

    with app.app_context():
        assert GradeCatalog.query.count() == before + 1


def test_assign_grade_creates_history_and_closes_previous(hr_client, seed_company, app):
    with app.app_context():
        grade_a = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=True)
        grade_b = GradeCatalog(name="Middle", rank=2, min_years=1.5, is_active=True)
        db.session.add_all([grade_a, grade_b])
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд Тест",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=grade_a.id,
                assigned_date=date(2024, 1, 1),
            )
        )
        db.session.commit()
        employment_id = employment.id
        grade_b_id = grade_b.id

    response = hr_client.post(
        "/api/grades/assign",
        json={
            "employment_id": employment_id,
            "grade_id": grade_b_id,
            "assigned_date": "2025-06-01",
            "basis": "Повышение",
        },
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["grade"]["name"] == "Middle"
    assert data["grade_date"] == "2025-06-01"

    with app.app_context():
        history = (
            EmployeeGradeHistory.query.filter_by(employment_id=employment_id)
            .order_by(EmployeeGradeHistory.assigned_date.asc())
            .all()
        )
        assert len(history) == 2
        assert history[0].valid_to == date(2025, 6, 1)
        assert history[1].grade_id == grade_b_id


def test_assign_grade_rejects_inactive_grade(hr_client, seed_company, app):
    with app.app_context():
        grade = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=False)
        db.session.add(grade)
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд Тест",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.commit()
        employment_id = employment.id
        grade_id = grade.id

    response = hr_client.post(
        "/api/grades/assign",
        json={
            "employment_id": employment_id,
            "grade_id": grade_id,
            "assigned_date": "2025-06-01",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "Grade is inactive"


def test_compute_grade_eligibility_uses_min_years(app, seed_company):
    with app.app_context():
        grade_a = GradeCatalog(name="Junior", rank=1, min_years=1.5, is_active=True)
        grade_b = GradeCatalog(name="Middle", rank=2, min_years=2, is_active=True)
        db.session.add_all([grade_a, grade_b])
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд Тест",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=grade_a.id,
                assigned_date=date(2024, 1, 15),
            )
        )
        db.session.commit()

        eligibility = compute_grade_eligibility(employment, date(2024, 6, 1))
        assert eligibility["next_grade"].name == "Middle"
        assert eligibility["eligible_date"] == date(2025, 7, 15)


def test_compute_grade_eligibility_max_rank_has_no_next_grade(app, seed_company):
    with app.app_context():
        grade = GradeCatalog(name="Lead", rank=1, min_years=2, is_active=True)
        db.session.add(grade)
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд Тест",
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

        eligibility = compute_grade_eligibility(employment, date(2024, 6, 1))
        assert eligibility["next_grade"] is None
        assert eligibility["eligible_date"] is None
