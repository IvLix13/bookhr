from datetime import date

from app.extensions import db
from app.models import EmployeeGradeHistory, GradeCatalog, Reward, RewardStatus
from app.services.employees import create_person_with_employment
from app.utils.dates import today_moscow


def _create_employment(company_id: int):
    _, employment = create_person_with_employment(
        company_id=company_id,
        full_name="Иван Иванов",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    db.session.commit()
    return employment


def test_create_reward_hr(hr_client, seed_company):
    employment = _create_employment(seed_company.id)

    response = hr_client.post(
        "/api/rewards",
        json={
            "employment_id": employment.id,
            "reward_type": "Благодарность",
            "status": "not_delivered",
            "directive_text": "Указ №1 от 01.01.2026",
            "notes": "Тест",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["reward_type"] == "Благодарность"
    assert payload["status"] == RewardStatus.NOT_DELIVERED.value
    assert payload["full_name"] == "Иван Иванов"
    assert payload["directive_text"] == "Указ №1 от 01.01.2026"


def test_create_reward_viewer_forbidden(viewer_client, seed_company):
    employment = _create_employment(seed_company.id)

    response = viewer_client.post(
        "/api/rewards",
        json={
            "employment_id": employment.id,
            "reward_type": "Благодарность",
        },
    )
    assert response.status_code == 403


def test_update_reward_status_to_delivered_sets_date(hr_client, seed_company, monkeypatch):
    employment = _create_employment(seed_company.id)
    monkeypatch.setattr("app.services.rewards.today_moscow", lambda: date(2026, 7, 28))

    create_response = hr_client.post(
        "/api/rewards",
        json={
            "employment_id": employment.id,
            "reward_type": "Премия",
        },
    )
    reward_id = create_response.get_json()["data"]["id"]

    response = hr_client.patch(
        f"/api/rewards/{reward_id}",
        json={"status": RewardStatus.DELIVERED.value},
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["status"] == RewardStatus.DELIVERED.value
    assert payload["delivered_date"] == "2026-07-28"


def test_update_reward_preserves_delivered_date(hr_client, seed_company):
    employment = _create_employment(seed_company.id)

    create_response = hr_client.post(
        "/api/rewards",
        json={
            "employment_id": employment.id,
            "reward_type": "Премия",
            "status": RewardStatus.DELIVERED.value,
            "delivered_date": "2026-06-01",
        },
    )
    reward_id = create_response.get_json()["data"]["id"]

    response = hr_client.patch(
        f"/api/rewards/{reward_id}",
        json={"notes": "Обновлено"},
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["delivered_date"] == "2026-06-01"
    assert payload["notes"] == "Обновлено"


def test_list_rewards_filter_by_company(admin_client, seed_company, app):
    employment = _create_employment(seed_company.id)
    with app.app_context():
        db.session.add(
            Reward(
                employment_id=employment.id,
                reward_type="Грамота",
                status=RewardStatus.IN_HR.value,
            )
        )
        db.session.commit()

    response = admin_client.get(f"/api/rewards?company_id={seed_company.id}")
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["reward_type"] == "Грамота"


def test_create_reward_requires_type(hr_client, seed_company):
    employment = _create_employment(seed_company.id)

    response = hr_client.post(
        "/api/rewards",
        json={
            "employment_id": employment.id,
            "reward_type": "   ",
        },
    )
    assert response.status_code == 400


def test_employee_list_includes_eligible_date(admin_client, seed_company, app):
    with app.app_context():
        grade_a = GradeCatalog(name="Junior", rank=1, min_months=12)
        grade_b = GradeCatalog(name="Middle", rank=2, min_months=12)
        db.session.add_all([grade_a, grade_b])
        db.session.flush()

        employment = _create_employment(seed_company.id)
        db.session.add(
            EmployeeGradeHistory(
                employment_id=employment.id,
                grade_id=grade_a.id,
                assigned_date=date(2025, 1, 15),
            )
        )
        db.session.commit()
        employment_id = employment.id

    response = admin_client.get(f"/api/employees?company_id={seed_company.id}&per_page=50")
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    employee = next(item for item in items if item["id"] == employment_id)
    assert employee["eligible_date"] == "2026-01-15"
