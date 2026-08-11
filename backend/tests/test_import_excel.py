from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook

from app.extensions import db
from app.models import (
    Company,
    EmployeeGradeHistory,
    Event,
    EventSource,
    GradeCatalog,
    ImportJob,
    ImportStatus,
    Passport,
    Person,
    Role,
    RoleName,
    User,
)
from app.services.employees import create_person_with_employment
from app.services.import_excel import confirm_import, dry_run_import, parse_workbook
from app.utils.dates import parse_flexible_date


def _write_workbook(path: Path, *, russian_dates: bool = False, as_datetime_cells: bool = False) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "ФИО",
            "Должность",
            "Грейд по должности",
            "Фактический грейд",
            "ВУЗ",
            "Окончание договора",
            "Дата получения текущего грейда",
            "Начало работы",
            "Срок окончания паспорта",
        ]
    )
    if as_datetime_cells:
        row = [
            "Тестов Тест Тестович",
            "Инженер",
            "Мидл",
            "Мидл",
            "Да",
            datetime(2026, 12, 1),
            datetime(2024, 3, 1),
            datetime(2021, 1, 10),
            datetime(2029, 8, 20),
        ]
    elif russian_dates:
        row = [
            "Тестов Тест Тестович",
            "Инженер",
            "Мидл",
            "Мидл",
            "Да",
            "1 декабря 2026 г.",
            "1 марта 2024 г.",
            "10 января 2021 г.",
            "20 августа 2029 г.",
        ]
    else:
        row = [
            "Тестов Тест Тестович",
            "Инженер",
            "Мидл",
            "Мидл",
            "Да",
            "01.12.2026",
            "01.03.2024",
            "10.01.2021",
            "20.08.2029",
        ]
    ws.append(row)
    wb.save(path)


def _seed_import_company():
    company = Company(name="Import Co")
    role = Role(name=RoleName.HR.value)
    db.session.add_all([company, role])
    db.session.flush()

    user = User(username="importer", full_name="Importer", role_id=role.id)
    user.set_password("secret123")
    db.session.add(user)
    db.session.add_all(
        [
            GradeCatalog(name="Мидл", rank=3, min_months=18),
            GradeCatalog(name="Сеньор", rank=4, min_months=24),
        ]
    )
    db.session.commit()
    return company, user


def test_parse_flexible_date_formats():
    assert parse_flexible_date("10.01.2021") == date(2021, 1, 10)
    assert parse_flexible_date("14 ноября 2026 г.") == date(2026, 11, 14)
    assert parse_flexible_date("14 ноября 2026") == date(2026, 11, 14)
    assert parse_flexible_date("2021-01-10 00:00:00") == date(2021, 1, 10)
    assert parse_flexible_date(datetime(2021, 1, 10, 15, 30)) == date(2021, 1, 10)
    assert parse_flexible_date("") is None


def test_confirm_import_runs_rule_engine(app, tmp_path):
    with app.app_context():
        company, user = _seed_import_company()

        path = tmp_path / "employees.xlsx"
        _write_workbook(path)

        job = ImportJob(
            company_id=company.id,
            filename=path.name,
            uploaded_by_id=user.id,
        )
        db.session.add(job)
        db.session.flush()

        rows = parse_workbook(path)
        dry_run_import(job, rows)
        db.session.commit()

        assert job.status == ImportStatus.VALIDATED.value
        assert job.summary["create"] == 1
        assert "uuid" not in (job.rows[0].raw_data or {})

        confirm_import(job)

        assert job.status == ImportStatus.CONFIRMED.value
        assert job.summary["created"] == 1
        assert job.summary["updated"] == 0
        assert job.rows[0].result == "created"
        events = Event.query.filter_by(
            company_id=company.id,
            source=EventSource.RULE.value,
        ).all()
        event_types = {event.event_type for event in events}
        assert "report" in event_types
        assert "grade" in event_types
        assert "passport" in event_types
        assert len(events) == 3


def test_confirm_import_accepts_datetime_cells(app, tmp_path):
    with app.app_context():
        company, user = _seed_import_company()
        path = tmp_path / "employees-dt.xlsx"
        _write_workbook(path, as_datetime_cells=True)

        job = ImportJob(company_id=company.id, filename=path.name, uploaded_by_id=user.id)
        db.session.add(job)
        db.session.flush()
        dry_run_import(job, parse_workbook(path))
        db.session.commit()

        confirm_import(job)
        assert job.status == ImportStatus.CONFIRMED.value
        assert job.summary["created"] == 1
        assert job.rows[0].result == "created"


def test_confirm_import_accepts_russian_long_dates(app, tmp_path):
    with app.app_context():
        company, user = _seed_import_company()
        path = tmp_path / "employees-ru.xlsx"
        _write_workbook(path, russian_dates=True)

        job = ImportJob(company_id=company.id, filename=path.name, uploaded_by_id=user.id)
        db.session.add(job)
        db.session.flush()
        dry_run_import(job, parse_workbook(path))
        db.session.commit()

        confirm_import(job)
        assert job.status == ImportStatus.CONFIRMED.value
        assert job.summary["created"] == 1


def test_ambiguous_requires_user_choice(app, tmp_path):
    with app.app_context():
        company, user = _seed_import_company()
        create_person_with_employment(
            company_id=company.id,
            full_name="Тестов Тест Тестович",
            hire_date=date(2019, 1, 1),
            title="Старый",
        )
        create_person_with_employment(
            company_id=company.id,
            full_name="Тестов Тест Тестович",
            hire_date=date(2020, 1, 1),
            title="Другой",
        )
        db.session.commit()

        path = tmp_path / "dupes.xlsx"
        _write_workbook(path)
        job = ImportJob(company_id=company.id, filename=path.name, uploaded_by_id=user.id)
        db.session.add(job)
        db.session.flush()
        dry_run_import(job, parse_workbook(path))
        db.session.commit()

        assert job.summary["ambiguous"] == 1
        assert job.rows[0].candidates and len(job.rows[0].candidates) == 2

        people_before = Person.query.count()
        confirm_import(job)
        assert Person.query.count() == people_before
        assert job.summary["skipped"] == 1
        assert job.rows[0].result == "skipped"

        target_uuid = job.rows[0].candidates[0]["uuid"]
        job.status = ImportStatus.VALIDATED.value
        db.session.commit()
        confirm_import(job, {job.rows[0].id: f"update:{target_uuid}"})
        assert job.summary["updated"] == 1
        assert job.rows[0].result == "updated"


def test_reimport_does_not_duplicate_passport_and_grade(app, tmp_path):
    with app.app_context():
        company, user = _seed_import_company()
        path = tmp_path / "once.xlsx"
        _write_workbook(path)

        job1 = ImportJob(company_id=company.id, filename=path.name, uploaded_by_id=user.id)
        db.session.add(job1)
        db.session.flush()
        dry_run_import(job1, parse_workbook(path))
        db.session.commit()
        confirm_import(job1)

        job2 = ImportJob(company_id=company.id, filename=path.name, uploaded_by_id=user.id)
        db.session.add(job2)
        db.session.flush()
        dry_run_import(job2, parse_workbook(path))
        db.session.commit()
        assert job2.summary["update"] == 1
        confirm_import(job2)

        assert Passport.query.count() == 1
        assert EmployeeGradeHistory.query.count() == 1
        assert job2.summary["updated"] == 1


def test_empty_university_does_not_overwrite(app, tmp_path):
    with app.app_context():
        company, user = _seed_import_company()
        person, _employment = create_person_with_employment(
            company_id=company.id,
            full_name="Тестов Тест Тестович",
            hire_date=date(2021, 1, 10),
            title="Инженер",
            has_university=True,
        )
        db.session.commit()

        wb = Workbook()
        ws = wb.active
        ws.append(["ФИО", "Начало работы", "ВУЗ"])
        ws.append(["Тестов Тест Тестович", "10.01.2021", ""])
        path = tmp_path / "uni.xlsx"
        wb.save(path)

        job = ImportJob(company_id=company.id, filename=path.name, uploaded_by_id=user.id)
        db.session.add(job)
        db.session.flush()
        dry_run_import(job, parse_workbook(path))
        db.session.commit()
        confirm_import(job)

        db.session.refresh(person)
        assert person.has_university is True
