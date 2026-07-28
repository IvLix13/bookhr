"""Pytest configuration."""

import pytest

from app import create_app
from app.extensions import db
from app.models import Company, Role, RoleName, User


@pytest.fixture()
def app():
    application = create_app("testing")

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _ensure_role(name: RoleName) -> Role:
    role = Role.query.filter_by(name=name.value).first()
    if not role:
        role = Role(name=name.value)
        db.session.add(role)
        db.session.commit()
    return role


def _create_user(username: str, role_name: RoleName, password: str = "secret123") -> User:
    role = _ensure_role(role_name)
    user = User(username=username, full_name=username.title(), role_id=role.id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, username: str, password: str = "secret123") -> None:
    response = client.post("/api/login", json={"username": username, "password": password})
    assert response.status_code == 200


@pytest.fixture()
def seed_company(app):
    with app.app_context():
        company = Company(name="Test Co")
        db.session.add(company)
        db.session.commit()
        yield company


@pytest.fixture()
def admin_client(client, seed_company):
    with client.application.app_context():
        _create_user("admin_user", RoleName.ADMIN)
    _login(client, "admin_user")
    return client


@pytest.fixture()
def hr_client(client, seed_company):
    with client.application.app_context():
        _create_user("hr_user", RoleName.HR)
    _login(client, "hr_user")
    return client


@pytest.fixture()
def viewer_client(client, seed_company):
    with client.application.app_context():
        _create_user("viewer_user", RoleName.VIEWER)
    _login(client, "viewer_user")
    return client
