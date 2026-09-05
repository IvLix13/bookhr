from datetime import date

from app.extensions import db
from app.models import (
    EducationStatus,
    EmployeeGradeHistory,
    Employment,
    Event,
    EventStatus,
    EventStatusHistory,
    GradeCatalog,
    PositionHistory,
)
from app.services.employees import create_person_with_employment, get_current_grade, get_current_position
from app.services.grades import assign_grade_to_employment, compute_grade_eligibility
from app.services.rule_engine import recalculate_employment_events


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


def test_create_grade_catalog_allows_duplicate_rank(admin_client):
    first = admin_client.post(
        "/api/grade-catalog",
        json={"name": "Middle A", "rank": 3, "min_years": 2},
    )
    second = admin_client.post(
        "/api/grade-catalog",
        json={"name": "Middle B", "rank": 3, "min_years": 2},
    )
    assert first.status_code == 201
    assert second.status_code == 201


def test_create_grade_catalog_rejects_invalid_min_years(admin_client):
    response = admin_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 1, "min_years": 1.25},
    )
    assert response.status_code == 400
    assert "0.1 year steps" in response.get_json()["message"]


def test_update_min_years_shifts_open_grade_events(admin_client, seed_company, app):
    with app.app_context():
        junior = GradeCatalog(name="JuniorShift", rank=1, min_years=1, is_active=True)
        middle = GradeCatalog(name="MiddleShift", rank=2, min_years=1, is_active=True)
        db.session.add_all([junior, middle])
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Каталог Срок",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
            education_status="yes",
        )
        assign_grade_to_employment(employment, junior, date(2026, 10, 1))
        recalculate_employment_events(employment)
        db.session.commit()
        junior_id = junior.id
        prep = Event.query.filter(
            Event.employment_id == employment.id,
            Event.rule_key.like("grade-preparation:%"),
        ).one()
        promo = Event.query.filter(
            Event.employment_id == employment.id,
            Event.rule_key.like("grade-promotion:%"),
        ).one()
        prep_id = prep.id
        promo_id = promo.id
        assert prep.event_date == date(2027, 9, 1)
        assert promo.event_date == date(2027, 10, 1)

    response = admin_client.patch(
        f"/api/grade-catalog/{junior_id}",
        json={"min_years": 2},
    )
    assert response.status_code == 200

    with app.app_context():
        history = EmployeeGradeHistory.query.filter_by(valid_to=None).one()
        assert history.required_months == 24
        prep = db.session.get(Event, prep_id)
        promo = db.session.get(Event, promo_id)
        assert prep is not None
        assert promo is not None
        assert prep.status == EventStatus.PLANNED.value
        assert promo.status == EventStatus.PLANNED.value
        assert prep.event_date == date(2028, 9, 1)
        assert promo.event_date == date(2028, 10, 1)
        assert EventStatusHistory.query.filter_by(
            event_id=promo_id,
            new_status=EventStatus.CANCELLED.value,
        ).count() == 0


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
            education_status="yes",
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


def _employment_with_grades(
    seed_company,
    *,
    actual: GradeCatalog,
    position: GradeCatalog | None,
    assigned_date: date = date(2024, 1, 15),
):
    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Грейд Тест",
        hire_date=date(2020, 1, 1),
        title="Инженер",
        position_grade_id=position.id if position else None,
        education_status="yes",
    )
    db.session.add(
        EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=actual.id,
            assigned_date=assigned_date,
        )
    )
    db.session.commit()
    return employment


def test_compute_grade_eligibility_uses_min_years(app, seed_company):
    with app.app_context():
        grade_a = GradeCatalog(name="Junior", rank=1, min_years=1.5, is_active=True)
        grade_b = GradeCatalog(name="Middle", rank=2, min_years=2, is_active=True)
        db.session.add_all([grade_a, grade_b])
        db.session.flush()
        employment = _employment_with_grades(
            seed_company,
            actual=grade_a,
            position=grade_b,
        )

        eligibility = compute_grade_eligibility(employment, date(2024, 6, 1))
        assert eligibility["next_grade"].name == "Middle"
        assert eligibility["eligible_date"] == date(2025, 7, 15)
        assert eligibility["is_available"] is False


def test_compute_grade_eligibility_available_once_term_passed(app, seed_company):
    with app.app_context():
        grade_a = GradeCatalog(name="Junior", rank=1, min_years=1.5, is_active=True)
        grade_b = GradeCatalog(name="Middle", rank=2, min_years=2, is_active=True)
        db.session.add_all([grade_a, grade_b])
        db.session.flush()
        employment = _employment_with_grades(
            seed_company,
            actual=grade_a,
            position=grade_b,
        )

        eligibility = compute_grade_eligibility(employment, date(2025, 8, 1))
        assert eligibility["eligible_date"] == date(2025, 7, 15)
        assert eligibility["is_available"] is True


def test_compute_grade_eligibility_requires_grade_below_position(app, seed_company):
    """Reaching the grade required by the position stops the promotion chain."""
    with app.app_context():
        grade_a = GradeCatalog(name="Junior", rank=1, min_years=1.5, is_active=True)
        grade_b = GradeCatalog(name="Middle", rank=2, min_years=2, is_active=True)
        db.session.add_all([grade_a, grade_b])
        db.session.flush()
        employment = _employment_with_grades(
            seed_company,
            actual=grade_b,
            position=grade_b,
        )

        eligibility = compute_grade_eligibility(employment, date(2030, 1, 1))
        assert eligibility["next_grade"] is None
        assert eligibility["eligible_date"] is None
        assert eligibility["is_available"] is False


def test_compute_grade_eligibility_without_position_grade(app, seed_company):
    with app.app_context():
        grade_a = GradeCatalog(name="Junior", rank=1, min_years=1.5, is_active=True)
        grade_b = GradeCatalog(name="Middle", rank=2, min_years=2, is_active=True)
        db.session.add_all([grade_a, grade_b])
        db.session.flush()
        employment = _employment_with_grades(
            seed_company,
            actual=grade_a,
            position=None,
        )

        eligibility = compute_grade_eligibility(employment, date(2030, 1, 1))
        assert eligibility["next_grade"] is None
        assert eligibility["eligible_date"] is None


def test_compute_grade_eligibility_max_rank_has_no_next_grade(app, seed_company):
    with app.app_context():
        grade = GradeCatalog(name="Lead", rank=1, min_years=2, is_active=True)
        db.session.add(grade)
        db.session.flush()
        employment = _employment_with_grades(
            seed_company,
            actual=grade,
            position=grade,
            assigned_date=date(2024, 1, 1),
        )

        eligibility = compute_grade_eligibility(employment, date(2024, 6, 1))
        assert eligibility["next_grade"] is None
        assert eligibility["eligible_date"] is None


def test_no_university_extra_year_is_frozen_at_rank_entry(app, seed_company):
    with app.app_context():
        junior = GradeCatalog(
            name="Junior",
            rank=1,
            min_years=1,
            extra_year_without_university=True,
            is_active=True,
        )
        middle = GradeCatalog(name="Middle", rank=2, min_years=1, is_active=True)
        db.session.add_all([junior, middle])
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Без Вуза",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            position_grade_id=middle.id,
            education_status=EducationStatus.NO.value,
        )
        history = assign_grade_to_employment(
            employment,
            junior,
            date(2024, 1, 1),
        )
        db.session.commit()

        assert history.required_months == 24
        assert compute_grade_eligibility(employment)["eligible_date"] == date(2026, 1, 1)

        employment.person.education_status = EducationStatus.YES.value
        junior.extra_year_without_university = False
        db.session.commit()

        assert compute_grade_eligibility(employment)["eligible_date"] == date(2026, 1, 1)


def test_same_rank_transfer_preserves_level_tenure(app, seed_company):
    with app.app_context():
        middle_a = GradeCatalog(name="Middle A", rank=2, min_years=1, is_active=True)
        middle_b = GradeCatalog(name="Middle B", rank=2, min_years=3, is_active=True)
        senior = GradeCatalog(name="Senior", rank=3, min_years=1, is_active=True)
        db.session.add_all([middle_a, middle_b, senior])
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Перевод Без Сброса",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            position_grade_id=senior.id,
            education_status=EducationStatus.YES.value,
        )
        first = assign_grade_to_employment(employment, middle_a, date(2024, 1, 1))
        second = assign_grade_to_employment(employment, middle_b, date(2024, 6, 1))
        db.session.commit()

        assert first.valid_to == date(2024, 6, 1)
        assert second.rank_started_at == date(2024, 1, 1)
        assert second.required_months == 12
        assert second.assigned_date == date(2024, 6, 1)
        assert compute_grade_eligibility(employment)["eligible_date"] == date(2025, 1, 1)


def test_eligibility_returns_all_candidates_on_nearest_higher_rank(app, seed_company):
    with app.app_context():
        junior = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=True)
        middle_b = GradeCatalog(name="Middle B", rank=3, min_years=1, is_active=True)
        middle_a = GradeCatalog(name="Middle A", rank=3, min_years=1, is_active=True)
        senior = GradeCatalog(name="Senior", rank=4, min_years=1, is_active=True)
        db.session.add_all([junior, middle_b, middle_a, senior])
        db.session.flush()
        employment = _employment_with_grades(
            seed_company,
            actual=junior,
            position=senior,
            assigned_date=date(2024, 1, 1),
        )

        eligibility = compute_grade_eligibility(employment)
        assert eligibility["next_rank"] == 3
        assert [grade.name for grade in eligibility["next_grade_candidates"]] == [
            "Middle A",
            "Middle B",
        ]
        assert eligibility["next_grade"] is None
        assert eligibility["requires_grade_choice"] is True


def test_eligibility_uses_rank_snapshot_after_catalog_edit(app, seed_company):
    with app.app_context():
        junior = GradeCatalog(name="Junior", rank=1, min_years=1, is_active=True)
        middle = GradeCatalog(name="Middle", rank=2, min_years=1, is_active=True)
        senior = GradeCatalog(name="Senior", rank=3, min_years=1, is_active=True)
        db.session.add_all([junior, middle, senior])
        db.session.flush()
        employment = _employment_with_grades(
            seed_company,
            actual=junior,
            position=senior,
            assigned_date=date(2024, 1, 1),
        )

        junior.rank = 4
        db.session.commit()

        eligibility = compute_grade_eligibility(employment)
        assert eligibility["next_rank"] == 2
        assert [grade.name for grade in eligibility["next_grade_candidates"]] == [
            "Middle"
        ]


def test_catalog_rejects_non_boolean_university_policy(admin_client):
    created = admin_client.post(
        "/api/grade-catalog",
        json={
            "name": "Middle",
            "rank": 2,
            "min_years": 1,
            "extra_year_without_university": "false",
        },
    )
    assert created.status_code == 400
    assert "must be boolean" in created.get_json()["message"]


def test_delete_unused_grade_catalog(admin_client, app):
    with app.app_context():
        grade = GradeCatalog(name="Junior", rank=1, min_years=1)
        db.session.add(grade)
        db.session.commit()
        grade_id = grade.id

    response = admin_client.delete(f"/api/grade-catalog/{grade_id}")
    assert response.status_code == 200

    with app.app_context():
        assert db.session.get(GradeCatalog, grade_id) is None


def test_delete_grade_catalog_unassigns_employees(admin_client, seed_company, app):
    with app.app_context():
        grade = GradeCatalog(name="Middle", rank=1, min_years=1, is_active=True)
        db.session.add(grade)
        db.session.flush()
        _, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Грейд На Удаление",
            hire_date=date(2020, 1, 1),
            title="Инженер",
            position_grade_id=grade.id,
        )
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=grade.id,
                assigned_date=date(2024, 1, 1),
            )
        )
        db.session.commit()
        grade_id = grade.id
        employment_id = employment.id

    listed = admin_client.get("/api/grade-catalog")
    assert listed.status_code == 200
    catalog = {item["id"]: item for item in listed.get_json()["data"]}
    assert catalog[grade_id]["in_use_count"] == 1

    response = admin_client.delete(f"/api/grade-catalog/{grade_id}")
    assert response.status_code == 200

    with app.app_context():
        assert db.session.get(GradeCatalog, grade_id) is None
        employment = db.session.get(Employment, employment_id)
        assert get_current_grade(employment) is None
        position = get_current_position(employment)
        assert position is not None
        assert position.position_grade_id is None
        assert EmployeeGradeHistory.query.filter_by(grade_id=grade_id).count() == 0
        assert PositionHistory.query.filter_by(position_grade_id=grade_id).count() == 0


def test_delete_grade_catalog_forbidden_for_viewer(viewer_client, app):
    with app.app_context():
        grade = GradeCatalog(name="Junior", rank=1, min_years=1)
        db.session.add(grade)
        db.session.commit()
        grade_id = grade.id

    response = viewer_client.delete(f"/api/grade-catalog/{grade_id}")
    assert response.status_code == 403
