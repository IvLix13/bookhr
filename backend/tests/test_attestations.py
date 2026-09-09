from datetime import date

from app.extensions import db
from app.models import Employment, EmploymentStatus, Person, PersonNameHistory


def _create_employment(company_id: int, full_name: str) -> Employment:
    person = Person()
    db.session.add(person)
    db.session.flush()

    db.session.add(
        PersonNameHistory(
            person_id=person.id,
            full_name=full_name,
            valid_from=date(2020, 1, 1),
        )
    )
    employment = Employment(
        person_id=person.id,
        company_id=company_id,
        status=EmploymentStatus.ACTIVE.value,
        hire_date=date(2020, 1, 1),
    )
    db.session.add(employment)
    db.session.commit()
    return employment


def test_attestations_list_active_employees(hr_client, seed_company):
    with hr_client.application.app_context():
        employment = _create_employment(seed_company.id, "Иванов Иван Иванович")
        employment.attestation_date = date(2026, 9, 15)
        db.session.commit()

    response = hr_client.get("/api/attestations")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0] == {
        "employment_id": employment.id,
        "full_name": "Иванов Иван Иванович",
        "attestation_date": "2026-09-15",
    }


def test_hr_can_set_and_clear_attestation_date(hr_client, seed_company):
    with hr_client.application.app_context():
        employment = _create_employment(seed_company.id, "Петров Петр Петрович")
        employment_id = employment.id

    response = hr_client.patch(
        f"/api/attestations/{employment_id}",
        json={"attestation_date": "2026-10-01"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["attestation_date"] == "2026-10-01"

    response = hr_client.patch(
        f"/api/attestations/{employment_id}",
        json={"attestation_date": None},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["attestation_date"] is None


def test_viewer_cannot_change_attestation_date(viewer_client, seed_company):
    with viewer_client.application.app_context():
        employment = _create_employment(seed_company.id, "Сидоров Сидор Сидорович")
        employment_id = employment.id

    response = viewer_client.patch(
        f"/api/attestations/{employment_id}",
        json={"attestation_date": "2026-10-01"},
    )

    assert response.status_code == 403


def test_attestation_update_is_company_scoped(hr_client, seed_company):
    with hr_client.application.app_context():
        employment = _create_employment(seed_company.id + 1, "Чужой Сотрудник")
        employment_id = employment.id

    response = hr_client.patch(
        f"/api/attestations/{employment_id}",
        json={"attestation_date": "2026-10-01"},
    )

    assert response.status_code == 404
