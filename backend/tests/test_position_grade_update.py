"""Verify position grade (грейд по должности) updates persist to the database."""

from datetime import date

from app.extensions import db
from app.models import Employment, GradeCatalog, ImportJob, ImportStatus, PositionHistory
from app.services.employees import get_current_position
from app.services.import_excel import confirm_import, dry_run_import, parse_workbook
from tests.test_import_excel import _seed_import_company, _write_workbook


def _seed_grades() -> tuple[int, int]:
    db.session.add_all(
        [
            GradeCatalog(name="Мидл", rank=3, min_years=1.5),
            GradeCatalog(name="Сеньор", rank=4, min_years=2),
        ]
    )
    db.session.commit()
    middle_id = GradeCatalog.query.filter_by(name="Мидл").first().id
    senior_id = GradeCatalog.query.filter_by(name="Сеньор").first().id
    return middle_id, senior_id


def test_patch_position_grade_only_updates_position_history(hr_client, seed_company):
    with hr_client.application.app_context():
        middle_id, senior_id = _seed_grades()

    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Тестов Тест Тестович",
            "title": "Инженер",
            "hire_date": "2021-01-10",
            "education_status": "yes",
            "position_grade_id": middle_id,
            "contract_term_years": 1,
            "contract_end": "2026-12-01",
            "passport_until": "2029-08-20",
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]

    with hr_client.application.app_context():
        employment = db.session.get(Employment, employment_id)
        pos = get_current_position(employment)
        assert pos.position_grade_id == middle_id
        count_before = PositionHistory.query.filter_by(employment_id=employment_id).count()

    updated = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"position_grade_id": senior_id},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["position_grade"]["id"] == senior_id

    with hr_client.application.app_context():
        employment = db.session.get(Employment, employment_id)
        pos = get_current_position(employment)
        assert pos.position_grade_id == senior_id
        count_after = PositionHistory.query.filter_by(employment_id=employment_id).count()
        assert count_after == count_before + 1


def test_import_updates_position_grade_when_title_unchanged(app, tmp_path):
    with app.app_context():
        company, user = _seed_import_company()
        middle_id = GradeCatalog.query.filter_by(name="Мидл").first().id
        senior_id = GradeCatalog.query.filter_by(name="Сеньор").first().id

        path = tmp_path / "employees.xlsx"
        _write_workbook(path, position_grade="Мидл")

        job = ImportJob(
            company_id=company.id,
            filename=path.name,
            uploaded_by_id=user.id,
        )
        db.session.add(job)
        db.session.flush()
        dry_run_import(job, parse_workbook(path))
        db.session.commit()
        confirm_import(job)
        db.session.commit()

        employment = Employment.query.filter_by(company_id=company.id).one()
        employment_id = employment.id
        assert get_current_position(employment).position_grade_id == middle_id

        path2 = tmp_path / "employees2.xlsx"
        _write_workbook(path2, position_grade="Сеньор")

        job2 = ImportJob(
            company_id=company.id,
            filename=path2.name,
            uploaded_by_id=user.id,
        )
        db.session.add(job2)
        db.session.flush()
        dry_run_import(job2, parse_workbook(path2))
        db.session.commit()
        confirm_import(job2)
        db.session.commit()

        employment = db.session.get(Employment, employment_id)
        assert get_current_position(employment).position_grade_id == senior_id
