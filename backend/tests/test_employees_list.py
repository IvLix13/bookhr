from datetime import date

from app.extensions import db
from app.models import Reward, RewardStatus
from app.services.employees import create_person_with_employment


def test_employees_list_pagination(admin_client, seed_company):
    for index in range(3):
        create_person_with_employment(
            company_id=seed_company.id,
            full_name=f"Сотрудник {index}",
            hire_date=date(2020, 1, index + 1),
            title="Специалист",
        )
    db.session.commit()

    response = admin_client.get(
        f"/api/employees?company_id={seed_company.id}&page=1&per_page=2"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["pages"] == 2
    assert data["page"] == 1
    assert data["per_page"] == 2


def test_employees_list_search_by_name(admin_client, seed_company):
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Уникальное Имя Тест",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Другой Человек",
        hire_date=date(2020, 2, 1),
        title="Аналитик",
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/employees?company_id={seed_company.id}&q=Уникальное"
    )
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["full_name"] == "Уникальное Имя Тест"


def test_employees_list_includes_latest_reward_status(admin_client, seed_company):
    _, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="С наградой",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Без награды",
        hire_date=date(2020, 2, 1),
        title="Аналитик",
    )
    db.session.add(
        Reward(
            employment_id=employment.id,
            reward_type="Благодарность",
            status=RewardStatus.IN_HR.value,
        )
    )
    db.session.flush()
    db.session.add(
        Reward(
            employment_id=employment.id,
            reward_type="Премия",
            status=RewardStatus.NOT_DELIVERED.value,
        )
    )
    db.session.commit()

    response = admin_client.get(f"/api/employees?company_id={seed_company.id}&q=наград")
    assert response.status_code == 200
    items = {item["full_name"]: item for item in response.get_json()["data"]["items"]}

    assert items["С наградой"]["reward_status"] == RewardStatus.NOT_DELIVERED.value
    assert items["Без награды"]["reward_status"] is None


def test_employees_list_sort_by_full_name(admin_client, seed_company):
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Яковлев Яков",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Алексеев Алексей",
        hire_date=date(2020, 2, 1),
        title="Аналитик",
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/employees?company_id={seed_company.id}&sort=full_name&direction=asc"
    )
    assert response.status_code == 200
    names = [item["full_name"] for item in response.get_json()["data"]["items"]]
    assert names == sorted(names)


def test_tenure_list_sort_by_full_name(admin_client, seed_company):
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Яковлев Яков",
        hire_date=date(2015, 1, 1),
        title="Инженер",
    )
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Алексеев Алексей",
        hire_date=date(2016, 2, 1),
        title="Аналитик",
    )
    db.session.commit()

    response = admin_client.get(
        f"/api/tenure?company_id={seed_company.id}&sort=full_name&direction=desc"
    )
    assert response.status_code == 200
    names = [item["full_name"] for item in response.get_json()["data"]["items"]]
    assert names == sorted(names, reverse=True)


def test_tenure_list_sort_by_tenure_years(admin_client, seed_company):
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Старый Стаж",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    create_person_with_employment(
        company_id=seed_company.id,
        full_name="Новый Стаж",
        hire_date=date(2020, 1, 1),
        title="Аналитик",
    )
    db.session.commit()

    response = admin_client.get("/api/tenure?sort=tenure_years&direction=desc")
    assert response.status_code == 200
    items = response.get_json()["data"]["items"]
    assert [item["full_name"] for item in items] == ["Старый Стаж", "Новый Стаж"]
    assert items[0]["tenure_years"] > items[1]["tenure_years"]
    assert items[0]["awards"]["10"]["milestone_date"] is not None


def test_employees_list_requires_auth(client):
    response = client.get("/api/employees")
    assert response.status_code in (401, 302)
