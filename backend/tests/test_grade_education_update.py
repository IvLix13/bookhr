"""Education edits update current tenure and its calendar events."""

from datetime import date

import pytest
from dateutil.relativedelta import relativedelta
from openpyxl import Workbook

from app.extensions import db
from app.models import EmployeeGradeHistory, Event, EventStatus, EventType, GradeCatalog
from app.services.employees import create_person_with_employment
from app.services.grades import assign_grade_to_employment, compute_grade_eligibility
from app.services.rule_engine import recalculate_employment_events


def _seed_employee(company_id, education, extra_year=True, same_rank=False):
    junior = GradeCatalog(
        name="Junior", rank=1, min_years=2,
        extra_year_without_university=extra_year,
    )
    middle = GradeCatalog(name="Middle", rank=2, min_years=1)
    db.session.add_all([junior, middle])
    db.session.flush()
    _, employment = create_person_with_employment(
        company_id=company_id, full_name="Образование Тест Сотрудника",
        hire_date=date(2020, 1, 1), title="Инженер",
        position_grade_id=middle.id, education_status=education,
    )
    history = assign_grade_to_employment(employment, junior, date(2030, 1, 1))
    closed = None
    if same_rank:
        sibling = GradeCatalog(
            name="Junior B", rank=1, min_years=2,
            extra_year_without_university=extra_year,
        )
        db.session.add(sibling)
        db.session.flush()
        closed = history
        history = assign_grade_to_employment(employment, sibling, date(2030, 6, 1))
    recalculate_employment_events(employment)
    db.session.commit()
    return employment, history, closed


def _assert_events(employment_id, eligible_date):
    events = Event.query.filter_by(
        employment_id=employment_id, event_type=EventType.GRADE.value,
    ).all()
    assert len(events) == 2
    assert {event.status for event in events} == {EventStatus.PLANNED.value}
    assert {event.event_date for event in events} == {
        eligible_date, eligible_date - relativedelta(months=1),
    }


@pytest.mark.parametrize("initial,updated,months", [("no", "yes", 24), ("yes", "no", 36)])
@pytest.mark.parametrize("extra_year", [True, False])
@pytest.mark.parametrize("same_rank", [True, False])
def test_card_education_change_recalculates_current_grade(
    hr_client, seed_company, initial, updated, months, extra_year, same_rank,
):
    with hr_client.application.app_context():
        employment, history, closed = _seed_employee(
            seed_company.id, initial, extra_year, same_rank,
        )
        employment_id, history_id = employment.id, history.id
        closed_id = closed.id if closed else None
        old_months = history.required_months
        assigned_date = history.assigned_date
        event_ids = {event.id for event in Event.query.all()}

    expected_months = months if extra_year else 24
    expected_date = date(2030, 1, 1) + relativedelta(months=expected_months)
    for _ in range(2):  # Repeated saves must neither reset tenure nor duplicate events.
        response = hr_client.patch(
            f"/api/employees/{employment_id}", json={"education_status": updated},
        )
        assert response.status_code == 200
        assert response.get_json()["data"]["eligible_date"] == expected_date.isoformat()
        with hr_client.application.app_context():
            history = db.session.get(EmployeeGradeHistory, history_id)
            assert history.required_months == expected_months
            assert history.education_status_at_rank_entry == updated
            assert history.rank_started_at == date(2030, 1, 1)
            assert history.assigned_date == assigned_date
            assert EmployeeGradeHistory.query.count() == (2 if same_rank else 1)
            if closed_id:
                closed = db.session.get(EmployeeGradeHistory, closed_id)
                assert closed.required_months == old_months
                assert closed.education_status_at_rank_entry == initial
            assert {event.id for event in Event.query.all()} == event_ids
            _assert_events(employment_id, expected_date)

    # Returning to the original value must also restore the original dates.
    response = hr_client.patch(
        f"/api/employees/{employment_id}", json={"education_status": initial},
    )
    assert response.status_code == 200
    old_date = date(2030, 1, 1) + relativedelta(months=old_months)
    assert response.get_json()["data"]["eligible_date"] == old_date.isoformat()
    with hr_client.application.app_context():
        _assert_events(employment_id, old_date)


@pytest.mark.parametrize("initial,updated,months", [("no", "yes", 24), ("yes", "no", 36)])
def test_import_education_change_recalculates_current_grade(
    hr_client, seed_company, tmp_path, initial, updated, months,
):
    with hr_client.application.app_context():
        employment, history, _ = _seed_employee(seed_company.id, initial)
        employment_id, history_id = employment.id, history.id
    path = tmp_path / "education.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["ФИО", "Должность", "Грейд по должности", "ВУЗ", "Начало работы"])
    ws.append([
        "Образование Тест Сотрудника", "Инженер", "Middle",
        "Да" if updated == "yes" else "Нет", "01.01.2020",
    ])
    wb.save(path)
    with path.open("rb") as handle:
        upload = hr_client.post(
            "/api/import/upload",
            data={"file": (handle, path.name), "import_type": "employees"},
            content_type="multipart/form-data",
        )
    assert upload.status_code == 201
    data = upload.get_json()["data"]
    assert data["summary"]["update"] == 1
    response = hr_client.post(f"/api/import/{data['id']}/confirm", json={"row_actions": {}})
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "confirmed"
    with hr_client.application.app_context():
        history = db.session.get(EmployeeGradeHistory, history_id)
        assert history.required_months == months
        assert history.education_status_at_rank_entry == updated
        assert history.rank_started_at == date(2030, 1, 1)
        expected_date = date(2030, 1, 1) + relativedelta(months=months)
        assert compute_grade_eligibility(history.employment)["eligible_date"] == expected_date
        _assert_events(employment_id, expected_date)
