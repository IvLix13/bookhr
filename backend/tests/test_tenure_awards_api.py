from datetime import date

from app.extensions import db
from app.models import TenureAward
from app.services.employees import create_person_with_employment
from app.services.tenure import ensure_tenure_awards


def test_update_tenure_award_marks_received(hr_client, seed_company):
    person, _employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Награда Ручная",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    awards = ensure_tenure_awards(person.id, seed_company.id)
    db.session.commit()
    award = awards[0]

    response = hr_client.patch(
        f"/api/tenure/{award.id}",
        json={"is_received": True, "received_date": "2021-06-15"},
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["is_received"] is True
    assert payload["received_date"] == "2021-06-15"
    assert payload["milestone_date"] == "2020-01-01"

    db.session.refresh(award)
    assert award.is_received is True
    assert award.received_date == date(2021, 6, 15)


def test_update_tenure_award_clears_received_date(hr_client, seed_company):
    person, _employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Награда Сброс",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    awards = ensure_tenure_awards(person.id, seed_company.id)
    award = awards[0]
    award.is_received = True
    award.received_date = date(2020, 1, 1)
    db.session.commit()

    response = hr_client.patch(
        f"/api/tenure/{award.id}",
        json={"is_received": False},
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["is_received"] is False
    assert payload["received_date"] is None

    db.session.refresh(award)
    assert award.is_received is False
    assert award.received_date is None


def test_update_tenure_award_recalculates_milestone_date(hr_client, seed_company):
    person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Награда Пересчёт",
        hire_date=date(2020, 1, 1),
        title="Инженер",
    )
    awards = ensure_tenure_awards(person.id, seed_company.id)
    db.session.commit()
    award = next(item for item in awards if item.milestone_years == 10)
    assert award.milestone_date == date(2030, 1, 1)

    employment.hire_date = date(2010, 1, 1)
    db.session.commit()

    response = hr_client.patch(
        f"/api/tenure/{award.id}",
        json={"is_received": True},
    )
    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["milestone_date"] == "2020-01-01"
    assert payload["received_date"] == "2020-01-01"


def test_update_tenure_award_viewer_forbidden(viewer_client, seed_company):
    person, _employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Награда Защита",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    awards = ensure_tenure_awards(person.id, seed_company.id)
    db.session.commit()

    response = viewer_client.patch(
        f"/api/tenure/{awards[0].id}",
        json={"is_received": True},
    )
    assert response.status_code == 403
