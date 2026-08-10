from datetime import date

from app.extensions import db
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


def test_employees_list_requires_auth(client):
    response = client.get("/api/employees")
    assert response.status_code in (401, 302)
