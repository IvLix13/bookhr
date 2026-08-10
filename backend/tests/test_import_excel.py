from pathlib import Path

from openpyxl import Workbook

from app.extensions import db
from app.models import (
    Company,
    Event,
    EventSource,
    GradeCatalog,
    ImportJob,
    ImportStatus,
    Role,
    RoleName,
    User,
)
from app.services.import_excel import confirm_import, dry_run_import, parse_workbook


def _write_workbook(path: Path) -> None:
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
    ws.append(
        [
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
    )
    wb.save(path)


def test_confirm_import_runs_rule_engine(app, tmp_path):
    with app.app_context():
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

        confirm_import(job)

        assert job.status == ImportStatus.CONFIRMED.value
        events = Event.query.filter_by(
            company_id=company.id,
            source=EventSource.RULE.value,
        ).all()
        event_types = {event.event_type for event in events}
        assert "report" in event_types
        assert "grade" in event_types
        assert "passport" in event_types
        assert len(events) == 3
