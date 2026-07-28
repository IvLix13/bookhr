from app.extensions import db
from app.models import GradeCatalog, Role, RoleName, User


def _ensure_roles():
    for role_name in RoleName:
        if not Role.query.filter_by(name=role_name.value).first():
            db.session.add(Role(name=role_name.value))
    db.session.commit()


def test_create_grade_catalog_as_admin(admin_client, app):
    with app.app_context():
        before = GradeCatalog.query.count()

    response = admin_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 10, "min_months": 24},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["name"] == "Lead"

    with app.app_context():
        assert GradeCatalog.query.count() == before + 1


def test_create_grade_catalog_forbidden_for_viewer(viewer_client):
    response = viewer_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 11, "min_months": 24},
    )
    assert response.status_code == 403


def test_create_grade_catalog_forbidden_for_hr(hr_client):
    response = hr_client.post(
        "/api/grade-catalog",
        json={"name": "Lead", "rank": 12, "min_months": 24},
    )
    assert response.status_code == 403
