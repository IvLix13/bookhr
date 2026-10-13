from datetime import date

import pytest

from app.extensions import db
from app.models import (
    Company,
    Employment,
    EmploymentStatus,
    Event,
    EventStatusHistory,
    Person,
    PersonNameHistory,
    Role,
    User,
)
from app.services.attestations import (
    find_attestation_events,
    preparation_date,
    set_attestation_date,
)
from app.services.rule_engine import run_rule_engine


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
        employment_id = employment.id
        employment.attestation_date = date(2026, 9, 15)
        db.session.commit()

    response = hr_client.get("/api/attestations")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0] == {
        "employment_id": employment_id,
        "full_name": "Иванов Иван Иванович",
        "attestation_date": "2026-09-15",
        "attestation_preparation_date": "2026-09-01",
        "attestation_event_id": None,
        "attestation_status": None,
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
        other_company = Company(name="Other Co")
        db.session.add(other_company)
        db.session.commit()
        employment = _create_employment(other_company.id, "Чужой Сотрудник")
        employment_id = employment.id

    response = hr_client.patch(
        f"/api/attestations/{employment_id}",
        json={"attestation_date": "2026-10-01"},
    )

    assert response.status_code == 404


@pytest.fixture()
def attestation(hr_client, seed_company, monkeypatch):
    for module in ("attestations", "events", "rule_engine"):
        monkeypatch.setattr(
            f"app.services.{module}.today_moscow", lambda: date(2026, 10, 13)
        )
    with hr_client.application.app_context():
        employment_id = _create_employment(seed_company.id, "Иван Иванов").id
    response = hr_client.patch(
        f"/api/attestations/{employment_id}", json={"attestation_date": "2026-10-30"}
    )
    assert response.status_code == 200
    with hr_client.application.app_context():
        events = find_attestation_events(db.session.get(Employment, employment_id))
        return employment_id, {kind: event.id for kind, event in events.items()}


@pytest.mark.parametrize(
    "conduct,expected",
    [
        (date(2026, 10, 30), date(2026, 10, 16)),
        (date(2026, 11, 6), date(2026, 10, 23)),
        (date(2028, 3, 1), date(2028, 2, 16)),
        (date(2027, 1, 5), date(2026, 12, 22)),
        (None, None),
    ],
)
def test_preparation_is_fourteen_calendar_days(conduct, expected):
    assert preparation_date(conduct) == expected


def test_rule_run_and_both_edit_paths_keep_event_ids(
    hr_client, attestation, seed_company
):
    employment_id, event_ids = attestation
    with hr_client.application.app_context():
        history_count = EventStatusHistory.query.count()
        run_rule_engine(seed_company.id)
        run_rule_engine(seed_company.id)
        db.session.commit()
        assert Event.query.count() == 2
        assert EventStatusHistory.query.count() == history_count
    for endpoint, field in (
        (f"/api/attestations/{employment_id}", "attestation_date"),
        (f"/api/events/{event_ids['attestation']}", "event_date"),
    ):
        response = hr_client.patch(endpoint, json={field: "2026-11-06"})
        assert response.status_code == 200
        with hr_client.application.app_context():
            assert db.session.get(Employment, employment_id).attestation_date == date(
                2026, 11, 6
            )
            assert db.session.get(Event, event_ids["attestation"]).event_date == date(
                2026, 11, 6
            )
            assert db.session.get(
                Event, event_ids["attestation_preparation"]
            ).event_date == date(2026, 10, 23)
            assert Event.query.count() == 2


@pytest.mark.parametrize("kind", ["attestation", "attestation_preparation"])
def test_completion_is_independent_and_reopen_preserves_date(
    hr_client, attestation, kind
):
    employment_id, ids = attestation
    other = "attestation_preparation" if kind == "attestation" else "attestation"
    response = hr_client.post(
        f"/api/events/{ids[kind]}/complete", json={"comment": "Готово"}
    )
    assert response.status_code == 200
    with hr_client.application.app_context():
        assert db.session.get(Event, ids[other]).status == "planned"
        assert Event.query.count() == 2
    row = hr_client.get(f"/api/attestations/{employment_id}").get_json()["data"]
    assert row["attestation_status"] == (
        "completed" if kind == "attestation" else "planned"
    )
    response = hr_client.post(f"/api/events/{ids[kind]}/reopen")
    assert response.status_code == 200
    assert response.get_json()["data"]["event_date"] == (
        "2026-10-30" if kind == "attestation" else "2026-10-16"
    )


def test_correct_completed_date_preserves_both_facts_and_history(
    hr_client, attestation
):
    employment_id, ids = attestation
    for event_id in ids.values():
        assert (
            hr_client.post(
                f"/api/events/{event_id}/complete", json={"comment": "Выполнено"}
            ).status_code
            == 200
        )
    with hr_client.application.app_context():
        snapshots = {
            event.id: (
                event.completed_at,
                event.completed_by_id,
                event.completion_comment,
            )
            for event in Event.query.all()
        }
        history_count = EventStatusHistory.query.count()
    for url, field, new_date in (
        (f"/api/events/{ids['attestation']}", "event_date", "2026-11-06"),
        (f"/api/attestations/{employment_id}", "attestation_date", "2026-11-13"),
    ):
        assert hr_client.patch(url, json={field: new_date}).status_code == 200
    with hr_client.application.app_context():
        assert EventStatusHistory.query.count() == history_count
        for event in Event.query.all():
            assert event.status == "completed"
            assert (
                event.completed_at,
                event.completed_by_id,
                event.completion_comment,
            ) == snapshots[event.id]
        assert db.session.get(Event, ids["attestation_preparation"]).event_date == date(
            2026, 10, 30
        )


def test_past_preparation_is_not_clamped_and_future_move_resets_overdue(
    hr_client, attestation
):
    employment_id, ids = attestation
    response = hr_client.patch(
        f"/api/attestations/{employment_id}", json={"attestation_date": "2026-10-20"}
    )
    assert response.status_code == 200
    with hr_client.application.app_context():
        event = db.session.get(Event, ids["attestation_preparation"])
        assert event.event_date == date(2026, 10, 6)
        assert event.status == "overdue"
    assert (
        hr_client.patch(
            f"/api/attestations/{employment_id}",
            json={"attestation_date": "2026-11-06"},
        ).status_code
        == 200
    )
    with hr_client.application.app_context():
        assert db.session.get(Event, ids["attestation_preparation"]).status == "planned"


@pytest.mark.parametrize("comment", ["Не проводить", "Attestation date cleared"])
def test_clear_cancels_open_events_restores_only_technical_cancellations(
    hr_client, attestation, comment
):
    employment_id, ids = attestation
    # A deliberate cancellation stays cancelled even across clearing/restoring.
    assert (
        hr_client.post(
            f"/api/events/{ids['attestation']}/cancel", json={"comment": comment}
        ).status_code
        == 200
    )
    response = hr_client.patch(
        f"/api/attestations/{employment_id}", json={"attestation_date": None}
    )
    assert response.status_code == 200
    row = response.get_json()["data"]
    assert row["attestation_event_id"] is None
    assert row["attestation_status"] is None
    assert row["attestation_preparation_date"] is None
    assert hr_client.post(f"/api/events/{ids['attestation']}/reopen").status_code == 400
    assert (
        hr_client.patch(
            f"/api/attestations/{employment_id}",
            json={"attestation_date": "2026-11-06"},
        ).status_code
        == 200
    )
    with hr_client.application.app_context():
        assert db.session.get(Event, ids["attestation"]).status == "cancelled"
        assert db.session.get(Event, ids["attestation_preparation"]).status == "planned"
        assert Event.query.count() == 2
    assert hr_client.post(f"/api/events/{ids['attestation']}/reopen").status_code == 200


def test_clear_preserves_completed_preparation(hr_client, attestation):
    employment_id, ids = attestation
    assert (
        hr_client.post(
            f"/api/events/{ids['attestation_preparation']}/complete"
        ).status_code
        == 200
    )
    assert (
        hr_client.patch(
            f"/api/attestations/{employment_id}", json={"attestation_date": None}
        ).status_code
        == 200
    )
    with hr_client.application.app_context():
        assert (
            db.session.get(Event, ids["attestation_preparation"]).status == "completed"
        )
        assert db.session.get(Event, ids["attestation"]).status == "cancelled"
    details = hr_client.get(f"/api/events/{ids['attestation_preparation']}").get_json()[
        "data"
    ]
    assert details["attestation_mutation_blocked_reason"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "Wrong"},
        {"employment_id": None},
        {"event_date": None},
        {"event_date": "0001-01-01"},
    ],
)
def test_invalid_event_patch_is_atomic(hr_client, attestation, payload):
    employment_id, ids = attestation
    response = hr_client.patch(f"/api/events/{ids['attestation']}", json=payload)
    assert response.status_code in {400, 409}
    with hr_client.application.app_context():
        assert db.session.get(Employment, employment_id).attestation_date == date(
            2026, 10, 30
        )
        assert db.session.get(Event, ids["attestation"]).event_date == date(
            2026, 10, 30
        )
        assert db.session.get(Event, ids["attestation_preparation"]).event_date == date(
            2026, 10, 16
        )


def test_preparation_date_cannot_be_edited_and_automatic_types_cannot_be_created(
    hr_client, attestation
):
    employment_id, ids = attestation
    assert (
        hr_client.patch(
            f"/api/events/{ids['attestation_preparation']}",
            json={"event_date": "2026-11-01"},
        ).status_code
        == 409
    )
    for kind in ids:
        assert (
            hr_client.post(
                "/api/events",
                json={
                    "title": "Ручное",
                    "event_type": kind,
                    "event_date": "2026-11-01",
                    "employment_id": employment_id,
                },
            ).status_code
            == 400
        )
    with hr_client.application.app_context():
        assert Event.query.count() == 2


@pytest.mark.parametrize("action", ["complete", "cancel", "reopen", "patch"])
def test_inactive_employee_events_cannot_be_mutated(hr_client, attestation, action):
    employment_id, ids = attestation
    with hr_client.application.app_context():
        employment = db.session.get(Employment, employment_id)
        employment.status = EmploymentStatus.DISMISSED.value
        from app.services.rule_engine import recalculate_employment_events

        recalculate_employment_events(employment)
        db.session.commit()
    url = f"/api/events/{ids['attestation']}"
    response = (
        hr_client.patch(url, json={"event_date": "2026-11-06"})
        if action == "patch"
        else hr_client.post(f"{url}/{action}", json={"comment": "test"})
    )
    assert response.status_code in {400, 409}
    with hr_client.application.app_context():
        assert db.session.get(Event, ids["attestation"]).status == "cancelled"
        assert db.session.get(Employment, employment_id).attestation_date == date(
            2026, 10, 30
        )


def test_new_column_sorts_on_server_across_pages(hr_client, seed_company):
    with hr_client.application.app_context():
        for name, conduct in [("Я", date(2030, 11, 6)), ("А", date(2030, 10, 30))]:
            employment = _create_employment(seed_company.id, name)
            employment.attestation_date = conduct
        db.session.commit()
    response = hr_client.get(
        "/api/attestations?sort=attestation_preparation_date&direction=asc&per_page=1&page=1"
    )
    payload = response.get_json()["data"]
    assert payload["total"] == 2
    assert payload["items"][0]["attestation_preparation_date"] == "2030-10-16"
    payload = hr_client.get(
        "/api/attestations?sort=attestation_preparation_date&direction=desc&per_page=1"
    ).get_json()["data"]
    assert payload["items"][0]["attestation_preparation_date"] == "2030-10-23"


def test_attestation_events_visible_in_calendar_feed_and_attention(
    hr_client, attestation
):
    employment_id, ids = attestation
    events = hr_client.get("/api/events?from=2026-10-01&to=2026-10-31").get_json()[
        "data"
    ]["items"]
    assert {event["id"] for event in events} == set(ids.values())
    upcoming = hr_client.get("/api/events/upcoming").get_json()["data"]
    assert {event["id"] for event in upcoming} == set(ids.values())
    hr_client.patch(
        f"/api/attestations/{employment_id}", json={"attestation_date": "2026-10-20"}
    )
    attention = hr_client.get("/api/attention?categories=events").get_json()["data"]
    assert str(ids["attestation_preparation"]) in str(attention)


def test_single_attestation_read_is_company_scoped_and_does_not_create_events(
    hr_client, seed_company
):
    with hr_client.application.app_context():
        company = Company(name="Other")
        db.session.add(company)
        db.session.flush()
        foreign_id = _create_employment(company.id, "Other employee").id
        local_id = _create_employment(seed_company.id, "Local employee").id
    assert hr_client.get(f"/api/attestations/{foreign_id}").status_code == 404
    row = hr_client.get(f"/api/attestations/{local_id}").get_json()["data"]
    assert row["attestation_preparation_date"] is None
    with hr_client.application.app_context():
        assert Event.query.count() == 0


@pytest.mark.parametrize("role_name,expected", [("admin", 200), ("viewer", 403)])
def test_attestation_read_and_mutations_obey_role(
    client, seed_company, role_name, expected
):
    with client.application.app_context():
        role = Role(name=role_name)
        db.session.add(role)
        db.session.flush()
        user = User(
            username=role_name,
            full_name=role_name,
            role_id=role.id,
            company_id=seed_company.id,
        )
        user.set_password("secret123")
        db.session.add(user)
        employment = _create_employment(seed_company.id, "Ролевой Сотрудник")
        set_attestation_date(employment, date(2030, 10, 30))
        db.session.commit()
        employment_id = employment.id
        event_id = find_attestation_events(employment)["attestation"].id
    assert (
        client.post(
            "/api/login", json={"username": role_name, "password": "secret123"}
        ).status_code
        == 200
    )
    assert client.get(f"/api/attestations/{employment_id}").status_code == 200
    assert (
        client.patch(
            f"/api/attestations/{employment_id}",
            json={"attestation_date": "2030-11-06"},
        ).status_code
        == expected
    )
    assert client.post(f"/api/events/{event_id}/complete").status_code == expected


def test_other_company_attestation_events_are_not_mutable(hr_client, seed_company):
    with hr_client.application.app_context():
        company = Company(name="Other company")
        db.session.add(company)
        db.session.flush()
        employment = _create_employment(company.id, "Чужой Сотрудник")
        set_attestation_date(employment, date(2030, 10, 30))
        db.session.commit()
        event_id = find_attestation_events(employment)["attestation"].id
    assert (
        hr_client.patch(
            f"/api/events/{event_id}", json={"event_date": "2030-11-06"}
        ).status_code
        == 404
    )
    for action in ["complete", "cancel", "reopen"]:
        assert (
            hr_client.post(
                f"/api/events/{event_id}/{action}", json={"comment": "test"}
            ).status_code
            == 404
        )


@pytest.mark.parametrize("invalid_date", ["0001-01-01", "not-a-date"])
def test_invalid_module_date_keeps_source_and_pair(
    hr_client, attestation, invalid_date
):
    employment_id, ids = attestation
    response = hr_client.patch(
        f"/api/attestations/{employment_id}", json={"attestation_date": invalid_date}
    )
    assert response.status_code == 400
    with hr_client.application.app_context():
        assert db.session.get(Employment, employment_id).attestation_date == date(
            2026, 10, 30
        )
        assert db.session.get(Event, ids["attestation_preparation"]).event_date == date(
            2026, 10, 16
        )
