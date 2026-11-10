"""Employee card creates and edits employment periods without changing saved identities."""
from datetime import date

from app.extensions import db
from app.models import Employment, EmploymentStatus
from app.services.tenure import employment_periods, total_tenure_years


def _create(hr_client, company_id, name="Периодов Тестовый Сотрудник", periods=None):
    body = {
        "company_id": company_id,
        "full_name": name,
        "title": "Инженер",
        "hire_date": periods[-1]["hire_date"] if periods else "2020-01-01",
        "education_status": "yes",
    }
    if periods is not None:
        body["periods"] = periods
    return hr_client.post("/api/employees", json=body)


def test_create_employee_with_three_periods(hr_client, seed_company):
    response = _create(hr_client, seed_company.id, periods=[
        {"hire_date": "2000-01-01", "dismissal_date": "2005-01-01"},
        {"hire_date": "2010-01-01", "dismissal_date": "2015-01-01"},
        {"hire_date": "2020-01-01", "dismissal_date": None},
    ])
    assert response.status_code == 201
    current_id = response.get_json()["data"]["id"]
    assert response.get_json()["data"]["hire_date"] == "2020-01-01"

    history = hr_client.get(f"/api/employees/{current_id}/periods")
    assert history.status_code == 200
    assert [(item["hire_date"], item["dismissal_date"]) for item in history.get_json()["data"]] == [
        ("2000-01-01", "2005-01-01"),
        ("2010-01-01", "2015-01-01"),
        ("2020-01-01", None),
    ]

    with hr_client.application.app_context():
        current = db.session.get(Employment, current_id)
        periods = employment_periods(current.person_id, seed_company.id)
        assert len(periods) == 3
        assert [period.status for period in periods] == [
            EmploymentStatus.DISMISSED.value,
            EmploymentStatus.DISMISSED.value,
            EmploymentStatus.ACTIVE.value,
        ]
        assert total_tenure_years(current.person_id, seed_company.id, date(2024, 1, 1)) == 14


def test_update_employee_adds_and_corrects_periods(hr_client, seed_company):
    response = _create(hr_client, seed_company.id, name="Повторно Принятый Сотрудник")
    assert response.status_code == 201
    initial_id = response.get_json()["data"]["id"]

    amended = hr_client.patch(f"/api/employees/{initial_id}", json={
        "hire_date": "2022-01-01",
        "periods": [
            {"id": initial_id, "hire_date": "2020-01-01", "dismissal_date": "2021-01-01"},
            {"id": None, "hire_date": "2022-01-01", "dismissal_date": None},
        ],
        "title": "Инженер",
        "education_status": "yes",
    })
    assert amended.status_code == 200
    latest_id = amended.get_json()["data"]["id"]
    assert latest_id != initial_id

    history = hr_client.get(f"/api/employees/{latest_id}/periods").get_json()["data"]
    assert len(history) == 2
    assert history[0]["id"] == initial_id
    assert history[1]["id"] == latest_id
    assert history[0]["status"] == "dismissed"
    assert history[1]["status"] == "active"

    corrected = hr_client.patch(f"/api/employees/{latest_id}", json={
        "hire_date": "2022-02-01",
        "periods": [
            {"id": initial_id, "hire_date": "2020-01-01", "dismissal_date": "2021-02-01"},
            {"id": latest_id, "hire_date": "2022-02-01", "dismissal_date": None},
        ],
    })
    assert corrected.status_code == 200
    assert corrected.get_json()["data"]["id"] == latest_id

    third = hr_client.patch(f"/api/employees/{latest_id}", json={
        "hire_date": "2024-01-01",
        "periods": [
            {"id": initial_id, "hire_date": "2020-01-01", "dismissal_date": "2021-02-01"},
            {"id": latest_id, "hire_date": "2022-02-01", "dismissal_date": "2023-01-01"},
            {"id": None, "hire_date": "2024-01-01", "dismissal_date": None},
        ],
    })
    assert third.status_code == 200
    final_id = third.get_json()["data"]["id"]
    assert final_id != latest_id
    history = hr_client.get(f"/api/employees/{final_id}/periods").get_json()["data"]
    assert len(history) == 3
    assert [item["id"] for item in history[:2]] == [initial_id, latest_id]

    with hr_client.application.app_context():
        assert db.session.get(Employment, initial_id).status == "dismissed"
        assert db.session.get(Employment, latest_id).status == "dismissed"
        assert db.session.get(Employment, final_id).status == "active"


def test_rejects_invalid_periods_without_mutating_history(hr_client, seed_company):
    response = _create(hr_client, seed_company.id, name="Проверка Неверных Дат")
    assert response.status_code == 201
    employment_id = response.get_json()["data"]["id"]

    variants = [
        [
            {"id": employment_id, "hire_date": "2020-01-01", "dismissal_date": None},
            {"id": None, "hire_date": "2022-01-01", "dismissal_date": None},
        ],
        [
            {"id": employment_id, "hire_date": "2020-01-01", "dismissal_date": "2022-02-01"},
            {"id": None, "hire_date": "2022-01-01", "dismissal_date": None},
        ],
        [
            {"id": employment_id, "hire_date": "2020-01-01", "dismissal_date": "2019-01-01"},
        ],
        [
            {"id": 999999, "hire_date": "2020-01-01", "dismissal_date": None},
        ],
    ]
    for periods in variants:
        rejected = hr_client.patch(f"/api/employees/{employment_id}", json={
            "hire_date": periods[-1]["hire_date"],
            "periods": periods,
        })
        assert rejected.status_code == 400
        with hr_client.application.app_context():
            active = db.session.get(Employment, employment_id)
            assert active.status == "active"
            assert active.hire_date == date(2020, 1, 1)
            assert len(employment_periods(active.person_id, seed_company.id)) == 1


def test_saved_period_cannot_be_removed_from_card(hr_client, seed_company):
    response = _create(hr_client, seed_company.id, name="Сохранённые Два Периода", periods=[
        {"hire_date": "2010-01-01", "dismissal_date": "2013-01-01"},
        {"hire_date": "2020-01-01", "dismissal_date": None},
    ])
    assert response.status_code == 201
    current_id = response.get_json()["data"]["id"]
    original = hr_client.get(f"/api/employees/{current_id}/periods").get_json()["data"]

    rejected = hr_client.patch(f"/api/employees/{current_id}", json={
        "hire_date": "2020-01-01",
        "periods": [original[-1]],
    })
    assert rejected.status_code == 400
    history = hr_client.get(f"/api/employees/{current_id}/periods").get_json()["data"]
    assert [item["id"] for item in history] == [item["id"] for item in original]


def test_periods_list_ignores_client_company_override(hr_client, seed_company):
    response = _create(hr_client, seed_company.id, name="Стаж Другой Компании")
    assert response.status_code == 201
    employment_id = response.get_json()["data"]["id"]
    history = hr_client.get(f"/api/employees/{employment_id}/periods?company_id=999999")
    assert history.status_code == 200
    assert history.get_json()["data"][0]["id"] == employment_id
    assert hr_client.get("/api/employees/999999/periods").status_code == 404
