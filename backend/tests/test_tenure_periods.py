from datetime import date
import uuid

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import Employment, EmploymentStatus, Person, TenureAward
from app.services.employees import create_person_with_employment, rehire_person
from app.services.tenure import (
    auto_mark_reached_awards,
    compute_milestone_date,
    ensure_tenure_awards,
    is_tenure_award_auto_eligible,
    is_tenure_award_pending,
    total_tenure_years,
)


def test_total_tenure_sums_employment_periods(seed_company):
    person, first = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Стаж Суммарный",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    first.status = EmploymentStatus.DISMISSED.value
    first.dismissal_date = date(2015, 1, 1)
    second = Employment(
        person_id=person.id,
        company_id=seed_company.id,
        hire_date=date(2018, 1, 1),
        status=EmploymentStatus.ACTIVE.value,
    )
    db.session.add(second)
    db.session.commit()

    assert total_tenure_years(person.id, seed_company.id, date(2023, 1, 1)) == 10
    assert compute_milestone_date(person.id, seed_company.id, 10) == date(2023, 1, 1)


def test_auto_mark_requires_cumulative_tenure(seed_company, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 1, 1))

    person, first = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Стаж Суммарный Авто",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    first.status = EmploymentStatus.DISMISSED.value
    first.dismissal_date = date(2015, 1, 1)
    second = Employment(
        person_id=person.id,
        company_id=seed_company.id,
        hire_date=date(2020, 1, 1),
        status=EmploymentStatus.ACTIVE.value,
    )
    db.session.add(second)
    db.session.commit()

    awards = ensure_tenure_awards(person.id, seed_company.id)
    marked = auto_mark_reached_awards(awards)
    assert marked == 1
    ten_year = next(award for award in awards if award.milestone_years == 10)
    assert ten_year.is_received is True
    assert ten_year.received_date == ten_year.milestone_date

    long_term, _ = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Стаж Без Перерыва",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    db.session.commit()
    long_awards = ensure_tenure_awards(long_term.id, seed_company.id)
    assert auto_mark_reached_awards(long_awards) == 2


def test_auto_mark_sets_received_date_from_cumulative_milestone(seed_company, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2031, 1, 1))

    person, first = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Дата Награды",
        hire_date=date(2000, 1, 1),
        title="Инженер",
    )
    first.status = EmploymentStatus.DISMISSED.value
    first.dismissal_date = date(2010, 1, 1)
    rehire_person(person, seed_company.id, date(2021, 1, 1), "Инженер")
    db.session.commit()

    awards = ensure_tenure_awards(person.id, seed_company.id)
    assert is_tenure_award_auto_eligible(awards[0]) is True
    assert auto_mark_reached_awards(awards) == 3
    assert awards[0].received_date == date(2010, 1, 1)
    assert awards[0].received_date == awards[0].milestone_date
    assert compute_milestone_date(person.id, seed_company.id, 10) == date(2010, 1, 1)


def test_milestone_date_uses_months_not_truncated_years(seed_company):
    person, first = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Стаж По Месяцам",
        hire_date=date(2000, 1, 1),
        title="Инженер",
    )
    first.status = EmploymentStatus.DISMISSED.value
    first.dismissal_date = date(2004, 12, 31)
    second = Employment(
        person_id=person.id,
        company_id=seed_company.id,
        hire_date=date(2010, 1, 1),
        status=EmploymentStatus.DISMISSED.value,
        dismissal_date=date(2014, 12, 31),
    )
    third = Employment(
        person_id=person.id,
        company_id=seed_company.id,
        hire_date=date(2020, 1, 1),
        status=EmploymentStatus.ACTIVE.value,
    )
    db.session.add_all([second, third])
    db.session.commit()

    milestone = compute_milestone_date(person.id, seed_company.id, 10)
    assert milestone == date(2020, 3, 1)
    assert total_tenure_years(person.id, seed_company.id, milestone) >= 10
    assert total_tenure_years(
        person.id,
        seed_company.id,
        milestone - relativedelta(days=1),
    ) < 10


def test_milestone_date_within_first_period(seed_company):
    person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Стаж В Первом Периоде",
        hire_date=date(2000, 1, 1),
        title="Инженер",
    )
    employment.status = EmploymentStatus.DISMISSED.value
    employment.dismissal_date = date(2015, 6, 1)
    db.session.commit()

    assert compute_milestone_date(person.id, seed_company.id, 10) == date(2010, 1, 1)


def test_tenure_award_pending_requires_lower_milestones(seed_company, monkeypatch):
    monkeypatch.setattr("app.services.tenure.today_moscow", lambda: date(2026, 1, 1))

    person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Pending Logic",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    awards = ensure_tenure_awards(person.id, seed_company.id)
    by_years = {award.milestone_years: award for award in awards}
    by_years[10].is_received = True
    by_years[10].received_date = date(2020, 1, 1)
    db.session.commit()

    assert is_tenure_award_pending(by_years[15], by_years) is True
    assert is_tenure_award_pending(by_years[20], by_years) is False
    by_years[15].is_received = True
    assert is_tenure_award_pending(by_years[20], by_years) is False


def test_rehire_limited_to_three_periods(hr_client, seed_company, app):
    with app.app_context():
        person = Person(uuid=uuid.UUID("00000000-0000-0000-0000-000000000099"))
        db.session.add(person)
        db.session.commit()
        person_id = person.id

    for index in range(3):
        response = hr_client.post(
            f"/api/employees/{person_id}/rehire",
            json={
                "hire_date": f"202{index}-01-01",
                "title": "Инженер",
            },
        )
        assert response.status_code == 201
        dismiss_id = response.get_json()["data"]["id"]
        assert (
            hr_client.post(
                f"/api/employees/{dismiss_id}/dismiss",
                json={"dismissal_date": f"202{index}-12-31"},
            ).status_code
            == 200
        )

    blocked = hr_client.post(
        f"/api/employees/{person_id}/rehire",
        json={"hire_date": "2025-01-01", "title": "Инженер"},
    )
    assert blocked.status_code == 400
    assert "лимит" in blocked.get_json()["message"].lower()


def test_tenure_awards_are_unique_per_person(seed_company):
    person, employment = create_person_with_employment(
        company_id=seed_company.id,
        full_name="Награды Один Раз",
        hire_date=date(2010, 1, 1),
        title="Инженер",
    )
    ensure_tenure_awards(person.id, seed_company.id)
    rehire_person(
        person,
        seed_company.id,
        date(2020, 1, 1),
        "Инженер",
    )
    ensure_tenure_awards(person.id, seed_company.id)
    db.session.commit()

    awards = TenureAward.query.filter_by(
        person_id=person.id,
        company_id=seed_company.id,
    ).all()
    assert len(awards) == 3
