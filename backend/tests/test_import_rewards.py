from datetime import date
from pathlib import Path

from openpyxl import Workbook

from app.extensions import db
from app.models import (
    Company,
    ImportJob,
    ImportStatus,
    ImportType,
    Reward,
    RewardStatus,
    Role,
    RoleName,
    User,
)
from app.services.employees import create_person_with_employment
from app.services.import_rewards import (
    confirm_rewards_import,
    dry_run_rewards_import,
    parse_rewards_workbook,
)


def _write_rewards_workbook(path: Path, rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "ФИО",
            "Вид поощрения",
            "Состояние",
            "Дата изменения",
            "Указание на вручение",
            "Дата вручения",
            "Примечание",
        ]
    )
    for row in rows:
        ws.append(row)
    wb.save(path)


def _seed_company_with_employee():
    company = Company(name="Rewards Import Co")
    role = Role(name=RoleName.HR.value)
    db.session.add_all([company, role])
    db.session.flush()

    user = User(username="rewards_importer", full_name="Importer", role_id=role.id)
    user.set_password("secret123")
    db.session.add(user)
    person, employment = create_person_with_employment(
        company_id=company.id,
        full_name="Иванов Иван Иванович",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    db.session.commit()
    return company, user, person, employment


def test_parse_and_create_reward_import(app, tmp_path):
    with app.app_context():
        company, user, _person, employment = _seed_company_with_employee()
        path = tmp_path / "rewards.xlsx"
        _write_rewards_workbook(
            path,
            [
                [
                    "Иванов Иван Иванович",
                    "Благодарность",
                    "В кадрах",
                    "10.01.2026",
                    "Указ №1",
                    "15.01.2026",
                    "Тест",
                ]
            ],
        )

        job = ImportJob(
            company_id=company.id,
            filename=path.name,
            import_type=ImportType.REWARDS.value,
            uploaded_by_id=user.id,
        )
        db.session.add(job)
        db.session.flush()

        rows = parse_rewards_workbook(path)
        dry_run_rewards_import(job, rows)
        db.session.commit()

        assert job.status == ImportStatus.VALIDATED.value
        assert job.summary["create"] == 1
        assert job.rows[0].action == "create"
        assert job.rows[0].raw_data["status_changed_date"] == "2026-01-10"

        confirm_rewards_import(job)

        assert job.status == ImportStatus.CONFIRMED.value
        assert job.summary["created"] == 1
        reward = Reward.query.filter_by(employment_id=employment.id).one()
        assert reward.reward_type == "Благодарность"
        assert reward.status == RewardStatus.IN_HR.value
        assert reward.status_changed_date == date(2026, 1, 10)
        assert reward.directive_text == "Указ №1"
        assert reward.delivered_date == date(2026, 1, 15)
        assert reward.notes == "Тест"


def test_rewards_import_updates_existing_by_type(app, tmp_path):
    with app.app_context():
        company, user, _person, employment = _seed_company_with_employee()
        existing = Reward(
            employment_id=employment.id,
            reward_type="Премия",
            status=RewardStatus.NOT_DELIVERED.value,
            notes="старое",
        )
        db.session.add(existing)
        db.session.commit()

        path = tmp_path / "rewards_update.xlsx"
        _write_rewards_workbook(
            path,
            [
                [
                    "Иванов Иван Иванович",
                    "премия",
                    "Вручено",
                    "20.02.2026",
                    "Указ №2",
                    "01.02.2026",
                    "новое",
                ]
            ],
        )

        job = ImportJob(
            company_id=company.id,
            filename=path.name,
            import_type=ImportType.REWARDS.value,
            uploaded_by_id=user.id,
        )
        db.session.add(job)
        db.session.flush()
        dry_run_rewards_import(job, parse_rewards_workbook(path))
        db.session.commit()

        assert job.summary["update"] == 1
        confirm_rewards_import(job)

        assert Reward.query.filter_by(employment_id=employment.id).count() == 1
        db.session.refresh(existing)
        assert existing.status == RewardStatus.DELIVERED.value
        assert existing.status_changed_date == date(2026, 2, 20)
        assert existing.notes == "новое"
        assert existing.delivered_date == date(2026, 2, 1)


def test_rewards_import_unknown_employee_is_error(app, tmp_path):
    with app.app_context():
        company, user, _person, _employment = _seed_company_with_employee()
        path = tmp_path / "rewards_missing.xlsx"
        _write_rewards_workbook(
            path,
            [["Неизвестный Сотрудник", "Благодарность", "Не вручено", "", "", "", ""]],
        )

        job = ImportJob(
            company_id=company.id,
            filename=path.name,
            import_type=ImportType.REWARDS.value,
            uploaded_by_id=user.id,
        )
        db.session.add(job)
        db.session.flush()
        dry_run_rewards_import(job, parse_rewards_workbook(path))
        db.session.commit()

        assert job.summary["error"] == 1
        assert job.rows[0].action == "error"
        assert "не найден" in (job.rows[0].errors or [""])[0].lower()


def test_rewards_import_rejects_invalid_changed_date(app, tmp_path):
    with app.app_context():
        company, user, _person, _employment = _seed_company_with_employee()
        path = tmp_path / "rewards_bad_date.xlsx"
        _write_rewards_workbook(
            path,
            [
                [
                    "Иванов Иван Иванович",
                    "Благодарность",
                    "Не вручено",
                    "не дата",
                    "",
                    "",
                    "",
                ]
            ],
        )

        job = ImportJob(
            company_id=company.id,
            filename=path.name,
            import_type=ImportType.REWARDS.value,
            uploaded_by_id=user.id,
        )
        db.session.add(job)
        db.session.flush()
        dry_run_rewards_import(job, parse_rewards_workbook(path))
        db.session.commit()

        assert job.summary["error"] == 1
        assert "дата изменения" in (job.rows[0].errors or [""])[0].lower()


def test_rewards_import_api_upload_and_confirm(hr_client, seed_company, app, tmp_path):
    with app.app_context():
        _person, employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name="Иванов Иван Иванович",
            hire_date=date(2020, 1, 1),
            title="Инженер",
        )
        db.session.commit()
        employment_id = employment.id
        company_id = seed_company.id

    path = tmp_path / "api_rewards.xlsx"
    _write_rewards_workbook(
        path,
        [
            [
                "Иванов Иван Иванович",
                "Грамота",
                "Не вручено",
                "05.03.2026",
                "",
                "",
                "api",
            ]
        ],
    )

    with path.open("rb") as handle:
        response = hr_client.post(
            "/api/import/upload",
            data={
                "file": (handle, path.name),
                "company_id": str(company_id),
                "import_type": "rewards",
            },
            content_type="multipart/form-data",
        )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["import_type"] == "rewards"
    assert payload["summary"]["create"] == 1
    job_id = payload["id"]

    confirm = hr_client.post(f"/api/import/{job_id}/confirm", json={"row_actions": {}})
    assert confirm.status_code == 200
    assert confirm.get_json()["data"]["status"] == "confirmed"

    with app.app_context():
        reward = Reward.query.filter_by(employment_id=employment_id).one()
        assert reward.reward_type == "Грамота"
        assert reward.status_changed_date == date(2026, 3, 5)
        assert reward.notes == "api"


def test_rewards_template_download(hr_client):
    response = hr_client.get("/api/import/template?import_type=rewards")
    assert response.status_code == 200
    assert (
        response.headers.get("Content-Disposition", "").find("rewards_template.xlsx")
        >= 0
    )
