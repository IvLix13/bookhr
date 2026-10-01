"""Viewer must not read import, rewards, stats, or tenure listing APIs."""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models import ImportJob, ImportStatus, User


VIEWER_FORBIDDEN_GETS = [
    "/api/rewards",
    "/api/rewards/statistics",
    "/api/rewards/statistics/export",
    "/api/stats",
    "/api/stats/manual",
    "/api/stats/manual/template",
    "/api/tenure",
    "/api/import/template",
    "/api/import/template?import_type=employees",
    "/api/import/template?import_type=rewards",
]


@pytest.mark.parametrize("path", VIEWER_FORBIDDEN_GETS)
def test_viewer_get_endpoints_forbidden(viewer_client, path):
    response = viewer_client.get(path)
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["success"] is False
    assert payload.get("data") is None


@pytest.mark.parametrize("path", VIEWER_FORBIDDEN_GETS)
def test_unauthenticated_get_endpoints_still_require_login(client, path):
    response = client.get(path)
    assert response.status_code in (401, 302)


def _create_import_job(app, seed_company, *, uploader_username: str) -> int:
    with app.app_context():
        user = User.query.filter_by(username=uploader_username).one()
        job = ImportJob(
            company_id=seed_company.id,
            filename="test.xlsx",
            uploaded_by_id=user.id,
            status=ImportStatus.VALIDATED.value,
        )
        db.session.add(job)
        db.session.commit()
        return job.id


def test_viewer_cannot_read_existing_import_job(viewer_client, app, seed_company):
    job_id = _create_import_job(app, seed_company, uploader_username="viewer_user")
    response = viewer_client.get(f"/api/import/{job_id}")
    assert response.status_code == 403
    assert response.get_json()["success"] is False


def test_viewer_cannot_read_missing_import_job(viewer_client):
    response = viewer_client.get("/api/import/999999")
    assert response.status_code == 403
    assert response.get_json()["success"] is False


def test_hr_can_read_import_job(hr_client, app, seed_company):
    job_id = _create_import_job(app, seed_company, uploader_username="hr_user")
    response = hr_client.get(f"/api/import/{job_id}")
    assert response.status_code == 200
    assert response.get_json()["data"]["id"] == job_id
