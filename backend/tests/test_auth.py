from unittest.mock import patch

from app.extensions import db
from app.models import AuthSource, Role, RoleName, User
from app.services.ldap_auth import LdapUserInfo


def test_login_flow(client, app):
    with app.app_context():
        db_role = Role.query.filter_by(name=RoleName.ADMIN.value).first()
        if not db_role:
            db_role = Role(name=RoleName.ADMIN.value)
            db.session.add(db_role)
            db.session.commit()

        user = User(username="tester", full_name="Tester", role_id=db_role.id)
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()

    response = client.post("/api/login", json={"username": "tester", "password": "secret123"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["username"] == "tester"


def test_login_invalid_credentials(client, app):
    with app.app_context():
        role = Role(name=RoleName.VIEWER.value)
        db.session.add(role)
        db.session.flush()
        user = User(username="viewer", full_name="Viewer", role_id=role.id)
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()

    response = client.post("/api/login", json={"username": "viewer", "password": "wrong"})
    assert response.status_code == 401


@patch("app.api.auth.authenticate_ldap_user")
def test_ldap_login_creates_user(mock_authenticate, client, app):
    app.config["LDAP_ENABLED"] = True
    app.config["LDAP_DEFAULT_ROLE"] = "viewer"
    app.config["LDAP_LOCAL_ADMIN_USERNAME"] = "admin"

    with app.app_context():
        role = Role(name=RoleName.VIEWER.value)
        db.session.add(role)
        db.session.commit()

    mock_authenticate.return_value = LdapUserInfo(username="ldap_user", full_name="LDAP User")

    response = client.post("/api/login", json={"username": "ldap_user", "password": "secret"})
    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="ldap_user").one()
        assert user.full_name == "LDAP User"
        assert user.auth_source == AuthSource.LDAP.value
        assert user.role.name == RoleName.VIEWER.value


@patch("app.api.auth.authenticate_ldap_user")
def test_ldap_login_preserves_existing_role(mock_authenticate, client, app):
    app.config["LDAP_ENABLED"] = True
    app.config["LDAP_DEFAULT_ROLE"] = "viewer"
    app.config["LDAP_LOCAL_ADMIN_USERNAME"] = "admin"

    with app.app_context():
        admin_role = Role(name=RoleName.ADMIN.value)
        db.session.add(admin_role)
        db.session.flush()
        user = User(
            username="ldap_admin",
            full_name="Old Name",
            role_id=admin_role.id,
            auth_source=AuthSource.LDAP.value,
        )
        db.session.add(user)
        db.session.commit()

    mock_authenticate.return_value = LdapUserInfo(username="ldap_admin", full_name="Updated Name")

    response = client.post("/api/login", json={"username": "ldap_admin", "password": "secret"})
    assert response.status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="ldap_admin").one()
        assert user.full_name == "Updated Name"
        assert user.role.name == RoleName.ADMIN.value


@patch("app.api.auth.authenticate_ldap_user")
def test_ldap_login_uses_local_admin_fallback(mock_authenticate, client, app):
    app.config["LDAP_ENABLED"] = True
    app.config["LDAP_LOCAL_ADMIN_USERNAME"] = "admin"

    with app.app_context():
        role = Role(name=RoleName.ADMIN.value)
        db.session.add(role)
        db.session.flush()
        user = User(username="admin", full_name="Admin", role_id=role.id)
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()

    response = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    mock_authenticate.assert_not_called()


@patch("app.api.auth.authenticate_ldap_user")
def test_ldap_login_invalid_credentials(mock_authenticate, client, app):
    app.config["LDAP_ENABLED"] = True
    app.config["LDAP_LOCAL_ADMIN_USERNAME"] = "admin"
    mock_authenticate.return_value = None

    response = client.post("/api/login", json={"username": "unknown", "password": "secret"})
    assert response.status_code == 401
