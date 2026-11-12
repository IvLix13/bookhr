from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import psycopg
import pytest
from openpyxl import load_workbook

from app.models import RoleName
from app.services import personal_document_errors as service
from conftest import _create_user, _login

URL = "/api/personal-document-errors/refresh"
EXPORT_URL = "/api/personal-document-errors/export"
PLAN = Path(__file__).resolve().parents[2] / "docs" / "2026-11-11-personal-document-errors-plan.md"


@pytest.fixture
def source(app, seed_company, monkeypatch):
    app.config.update(
        PERSONAL_DOCUMENT_ERRORS_ENABLED=True,
        PERSONAL_DOCUMENT_ERRORS_DSN="dbname=test-source",
        PERSONAL_DOCUMENT_ERRORS_BASE_URL="https://files.example.test/prefix/",
        PERSONAL_DOCUMENT_ERRORS_COMPANY_ID=seed_company.id,
    )
    # The shared API fixtures use SQLite. The advisory lock belongs to local PostgreSQL.
    monkeypatch.setattr(service, "_lock_snapshot", lambda connection, company_id: True)
    connect = MagicMock()
    monkeypatch.setattr(service.psycopg, "connect", connect)
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    return connect, cursor


def source_row(**overrides):
    return {
        **dict.fromkeys(
            (
                "grade_date_check", "post_date_check", "contract_date_check",
                "photo_date_check", "biography_date_check", "attestation_date_check",
                "passport_date_check",
            ),
            True,
        ),
        "id": 24,
        "ldnumber": "0007/а",
        "cardnumber": "0008",
        "grade": "Грейд",
        "f": "Иванов ",
        "i": "Иван",
        "o": None,
        "datebirth": None,
        "grade_date_check": False,
        **overrides,
    }


def test_every_entry_refreshes_with_the_approved_select(hr_client, source):
    connect, cursor = source
    cursor.__iter__.side_effect = [
        iter([
            source_row(),
            source_row(photo_date_check=False, passport_date_check=None),
            source_row(id=25, ldnumber="0002", f="Абрамов"),
        ]),
        iter([]),
    ]

    first = hr_client.post(URL)
    assert first.status_code == 200
    assert first.cache_control.no_store
    data = first.json["data"]
    assert data["state"] == "ready"
    assert data["last_success_at"]
    assert [item["external_id"] for item in data["items"]] == [25, 24]
    assert data["items"][1] == {
        "external_id": 24,
        "ldnumber": "0007/а",
        "cardnumber": "0008",
        "full_name": "Иванов Иван",
        "grade": "Грейд",
        "errors": ["grade", "photo"],
        "personal_file_url": "https://files.example.test/prefix/personalfile/0007%2F%D0%B0",
    }
    second = hr_client.post(URL).json["data"]
    assert second["state"] == "ready"
    assert second["items"] == []
    approved_select = PLAN.read_text(encoding="utf-8").split("```sql\n", 1)[1].split("\n```", 1)[0]
    assert [entry.args for entry in cursor.execute.call_args_list] == [(approved_select,), (approved_select,)]
    assert connect.call_count == 2
    assert connect.call_args.kwargs["autocommit"] is True
    assert connect.call_args.kwargs["connect_timeout"] > 0


def test_failed_attempts_keep_the_last_complete_snapshot(admin_client, source):
    connect, cursor = source
    connect.side_effect = psycopg.OperationalError("unavailable")
    initial = admin_client.post(URL).json["data"]
    assert initial["state"] == "source_error"
    assert initial["last_success_at"] is None
    assert initial["items"] == []

    connect.side_effect = None
    cursor.__iter__.return_value = iter([source_row()])
    success = admin_client.post(URL).json["data"]

    cursor.__iter__.return_value = iter([source_row(), source_row(id=25)])
    invalid = admin_client.post(URL).json["data"]
    assert invalid == {**success, "state": "source_error"}

    connect.side_effect = psycopg.OperationalError("unavailable")
    failure = admin_client.post(URL).json["data"]
    assert failure == invalid


def test_export_downloads_the_last_successful_snapshot_in_name_order(hr_client, source):
    connect, cursor = source
    cursor.__iter__.return_value = iter([
        source_row(grade="=1+1", photo_date_check=False),
        source_row(id=25, ldnumber="0002", f="Абрамов", grade=None),
    ])
    assert hr_client.post(URL).json["data"]["state"] == "ready"
    connect.side_effect = psycopg.OperationalError("unavailable")
    assert hr_client.post(URL).json["data"]["state"] == "source_error"

    response = hr_client.get(EXPORT_URL)

    assert response.status_code == 200
    assert response.cache_control.no_store
    assert "personal_document_errors.xlsx" in response.headers["Content-Disposition"]
    assert connect.call_count == 2
    with BytesIO(response.data) as output:
        sheet = load_workbook(output).active
        assert list(sheet.values) == [
            ("Грейд", "ФИО", "Ошибки"),
            ("—", "Абрамов Иван", 1),
            ("=1+1", "Иванов Иван", 2),
        ]
        assert sheet["A3"].data_type == "s"
        assert sheet["C3"].hyperlink.target == "https://files.example.test/prefix/personalfile/0007%2F%D0%B0"


def test_export_without_a_successful_snapshot_does_not_contact_source(hr_client, source):
    connect, _ = source
    assert hr_client.get(EXPORT_URL).status_code == 404
    connect.assert_not_called()


def test_anonymous_and_other_company_cannot_refresh(client, app, source):
    connect, _ = source
    assert client.post(URL).status_code == 401
    assert client.get(EXPORT_URL).status_code == 401
    _create_user("other_hr", RoleName.HR, company_id=app.config["PERSONAL_DOCUMENT_ERRORS_COMPANY_ID"] + 1)
    _login(client, "other_hr")
    assert client.post(URL).status_code == 403
    assert client.get(EXPORT_URL).status_code == 403
    connect.assert_not_called()


def test_viewer_cannot_refresh(viewer_client, source):
    connect, _ = source
    assert viewer_client.post(URL).status_code == 403
    assert viewer_client.get(EXPORT_URL).status_code == 403
    connect.assert_not_called()


def test_disabled_or_invalid_url_does_not_contact_source(hr_client, app, source):
    connect, _ = source
    app.config["PERSONAL_DOCUMENT_ERRORS_ENABLED"] = False
    assert hr_client.post(URL).json["data"]["state"] == "not_configured"
    app.config.update(
        PERSONAL_DOCUMENT_ERRORS_ENABLED=True,
        PERSONAL_DOCUMENT_ERRORS_BASE_URL="https://user:password@files.example.test",
    )
    assert hr_client.post(URL).json["data"]["state"] == "not_configured"
    connect.assert_not_called()
