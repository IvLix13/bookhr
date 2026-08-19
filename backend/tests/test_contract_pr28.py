"""PR #28: HR-entered contract end date and term, days_left from stored end."""

from __future__ import annotations

from datetime import date

import pytest

from app.models import Contract, Employment
from app.utils.dates import calculate_contract_start, today_moscow


@pytest.fixture
def fixed_today(monkeypatch):
    today = date(2026, 8, 19)
    monkeypatch.setattr("app.api.serializers.today_moscow", lambda: today)
    monkeypatch.setattr("app.services.attention.today_moscow", lambda: today)
    return today


def test_contract_end_and_days_left_use_hr_values_not_hire_date(
    hr_client, seed_company, fixed_today
):
    """End date is stored as entered; days_left = end_date - today (Moscow)."""
    hire_date = "2020-01-10"
    term_years = 3
    contract_end = "2027-07-10"
    expected_start = calculate_contract_start(date(2027, 7, 10), term_years)
    expected_days_left = (date(2027, 7, 10) - fixed_today).days

    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Проверка PR28",
            "title": "Инженер",
            "hire_date": hire_date,
            "education_status": "no",
            "contract_term_years": term_years,
            "contract_end": contract_end,
        },
    )
    assert created.status_code == 201
    employment_id = created.get_json()["data"]["id"]

    employees = hr_client.get("/api/employees")
    employee = next(
        item for item in employees.get_json()["data"]["items"] if item["id"] == employment_id
    )
    assert employee["contract_end"] == contract_end
    assert employee["contract_term_years"] == term_years
    assert employee["contract_days_left"] == expected_days_left

    contracts = hr_client.get("/api/contracts")
    row = next(
        item for item in contracts.get_json()["data"]["items"] if item["employment_id"] == employment_id
    )
    assert row["end_date"] == contract_end
    assert row["term_years"] == term_years
    assert row["days_left"] == expected_days_left
    assert row["start_date"] == expected_start.isoformat()
    assert expected_start != date.fromisoformat(hire_date)


def test_sync_active_contract_deactivates_duplicate_active_contracts(
    hr_client, seed_company, app
):
    created = hr_client.post(
        "/api/employees",
        json={
            "company_id": seed_company.id,
            "full_name": "Дубликат Договор",
            "title": "Инженер",
            "hire_date": "2020-01-01",
            "education_status": "no",
            "contract_term_years": 2,
            "contract_end": "2026-12-01",
        },
    )
    employment_id = created.get_json()["data"]["id"]

    stale = hr_client.post(
        "/api/contracts",
        json={
            "employment_id": employment_id,
            "term_years": 1,
            "end_date": "2025-06-01",
        },
    )
    assert stale.status_code == 201

    updated = hr_client.patch(
        f"/api/employees/{employment_id}",
        json={"contract_term_years": 3, "contract_end": "2028-06-01"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["contract_end"] == "2028-06-01"

    with app.app_context():
        from app.extensions import db

        employment = db.session.get(Employment, employment_id)
        active = [item for item in employment.contracts if item.is_active]
        assert len(active) == 1
        assert active[0].end_date == date(2028, 6, 1)
        assert active[0].start_date == calculate_contract_start(date(2028, 6, 1), 3)
