from app.extensions import db
from app.models import AuthSource, Role, RoleName, User


def _ensure_roles():
    for role_name in RoleName:
        if not Role.query.filter_by(name=role_name.value).first():
            db.session.add(Role(name=role_name.value))
    db.session.commit()


def test_list_roles_as_admin(admin_client, app):
    with app.app_context():
        _ensure_roles()

    response = admin_client.get("/api/roles")
    assert response.status_code == 200
    names = {item["name"] for item in response.get_json()["data"]}
    assert names == {"admin", "hr", "viewer"}


def test_list_users_requires_admin(viewer_client):
    response = viewer_client.get("/api/users")
    assert response.status_code == 403


def test_list_users_forbidden_for_hr(hr_client):
    response = hr_client.get("/api/users")
    assert response.status_code == 403


def test_create_user_forbidden_for_hr(hr_client):
    response = hr_client.post(
        "/api/users",
        json={
            "username": "new.user",
            "password": "StrongPass1",
            "full_name": "Новый Пользователь",
            "role": "viewer",
        },
    )
    assert response.status_code == 403


def test_create_local_user_as_admin(admin_client, app):
    with app.app_context():
        _ensure_roles()

    response = admin_client.post(
        "/api/users",
        json={
            "username": "new.user",
            "password": "StrongPass1",
            "full_name": "Новый Пользователь",
            "role": "hr",
        },
    )
    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["username"] == "new.user"
    assert payload["role"] == "hr"
    assert payload["auth_source"] == "local"
    assert payload["is_active"] is True


def test_create_user_rejects_weak_password(admin_client, app):
    with app.app_context():
        _ensure_roles()

    response = admin_client.post(
        "/api/users",
        json={
            "username": "weak.user",
            "password": "short",
            "full_name": "Weak User",
            "role": "viewer",
        },
    )
    assert response.status_code == 400


def test_update_user_role(admin_client, app):
    with app.app_context():
        _ensure_roles()
        role = Role.query.filter_by(name=RoleName.VIEWER.value).first()
        user = User(
            username="viewer.test",
            full_name="Viewer Test",
            role_id=role.id,
            auth_source=AuthSource.LOCAL.value,
            is_active=True,
        )
        user.set_password("StrongPass1")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    response = admin_client.patch(
        f"/api/users/{user_id}",
        json={"role": "hr"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["role"] == "hr"


def test_deactivate_user(admin_client, app):
    with app.app_context():
        _ensure_roles()
        admin_role = Role.query.filter_by(name=RoleName.ADMIN.value).first()
        hr_role = Role.query.filter_by(name=RoleName.HR.value).first()
        db.session.add(
            User(
                username="backup.admin",
                full_name="Backup Admin",
                role_id=admin_role.id,
                auth_source=AuthSource.LOCAL.value,
                is_active=True,
            )
        )
        target = User(
            username="deactivate.me",
            full_name="Deactivate Me",
            role_id=hr_role.id,
            auth_source=AuthSource.LOCAL.value,
            is_active=True,
        )
        target.set_password("StrongPass1")
        db.session.add(target)
        db.session.commit()
        user_id = target.id

    response = admin_client.patch(f"/api/users/{user_id}", json={"is_active": False})
    assert response.status_code == 200
    assert response.get_json()["data"]["is_active"] is False


def test_deactivate_last_admin_forbidden(admin_client, app):
    with app.app_context():
        _ensure_roles()
        admin_user = User.query.join(Role).filter(Role.name == RoleName.ADMIN.value).first()
        user_id = admin_user.id

    response = admin_client.patch(f"/api/users/{user_id}", json={"role": "hr"})
    assert response.status_code == 400
    assert "last active admin" in response.get_json()["message"]


def test_reset_password_local_user(admin_client, app):
    with app.app_context():
        _ensure_roles()
        role = Role.query.filter_by(name=RoleName.VIEWER.value).first()
        user = User(
            username="reset.me",
            full_name="Reset Me",
            role_id=role.id,
            auth_source=AuthSource.LOCAL.value,
            is_active=True,
        )
        user.set_password("StrongPass1")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    response = admin_client.post(
        f"/api/users/{user_id}/reset-password",
        json={"password": "NewStrongPass2"},
    )
    assert response.status_code == 200

    login = admin_client.post(
        "/api/login",
        json={"username": "reset.me", "password": "NewStrongPass2"},
    )
    assert login.status_code == 200


def test_reset_password_ldap_user_forbidden(admin_client, app):
    with app.app_context():
        _ensure_roles()
        role = Role.query.filter_by(name=RoleName.VIEWER.value).first()
        user = User(
            username="ldap.user",
            full_name="LDAP User",
            role_id=role.id,
            auth_source=AuthSource.LDAP.value,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    response = admin_client.post(
        f"/api/users/{user_id}/reset-password",
        json={"password": "NewStrongPass2"},
    )
    assert response.status_code == 400


def test_unlock_user(admin_client, app):
    with app.app_context():
        _ensure_roles()
        role = Role.query.filter_by(name=RoleName.VIEWER.value).first()
        user = User(
            username="locked.user",
            full_name="Locked User",
            role_id=role.id,
            auth_source=AuthSource.LOCAL.value,
            is_active=True,
            failed_login_attempts=0,
        )
        user.set_password("StrongPass1")
        for _ in range(5):
            user.record_failed_login()
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    response = admin_client.post(f"/api/users/{user_id}/unlock", json={})
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["is_locked"] is False
    assert data["failed_login_attempts"] == 0
