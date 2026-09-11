from datetime import date

from app.extensions import db
from app.models import TenureAward
from app.services.employees import create_person_with_employment, dismiss_employment
from app.services.tenure import ensure_tenure_awards


def test_tenure_get_does_not_create_awards(viewer_client, seed_company):
    _person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Только Чтение",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    db.session.commit()
    assert TenureAward.query.count() == 0

    response = viewer_client.get("/api/tenure")

    assert response.status_code == 200
    assert TenureAward.query.count() == 0
    row = response.get_json()["data"]["items"][0]
    assert row["employment_id"] == employment.id
    assert row["full_name"] == "Только Чтение"
    assert all(award["id"] is None for award in row["awards"].values())


def test_tenure_search_filters_before_batch_serialization(viewer_client, seed_company):
    for full_name in ("Иван Иванов", "Пётр Петров"):
        person, _employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name=full_name,
            hire_date=date(2018, 1, 1),
            title="Инженер",
        )
        ensure_tenure_awards(person.id, seed_company.id)
    db.session.commit()

    response = viewer_client.get("/api/tenure?q=Иван")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 1
    assert [item["full_name"] for item in data["items"]] == ["Иван Иванов"]


def test_tenure_pagination_keeps_response_contract(viewer_client, seed_company):
    for index in range(3):
        person, _employment = create_person_with_employment(
            company_id=seed_company.id,
            full_name=f"Сотрудник {index}",
            hire_date=date(2020 + index, 1, 1),
            title="Инженер",
        )
        ensure_tenure_awards(person.id, seed_company.id)
    db.session.commit()

    response = viewer_client.get(
        "/api/tenure?page=2&per_page=1&sort=full_name&direction=asc"
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["page"] == 2
    assert data["per_page"] == 1
    assert data["total"] == 3
    assert data["pages"] == 3
    assert len(data["items"]) == 1
    assert set(data["items"][0]["awards"]) == {"10", "15", "20"}


def test_dismissal_updates_unreceived_tenure_milestones(seed_company):
    person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Стаж Увольнение",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    awards = ensure_tenure_awards(person.id, seed_company.id)
    ten_year_award = next(award for award in awards if award.milestone_years == 10)
    assert ten_year_award.milestone_date == date(2030, 1, 1)

    dismiss_employment(employment, date(2025, 1, 1))
    db.session.commit()

    db.session.refresh(ten_year_award)
    assert ten_year_award.milestone_date == date(2025, 1, 1)
