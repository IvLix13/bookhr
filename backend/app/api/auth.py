"""Authentication API."""

from __future__ import annotations

from flask import current_app, session
from flask_login import login_required, login_user, logout_user

from app.api.helpers import api_response, get_json
from app.api.serializers import user_to_dict
from app.extensions import db
from app.models import AuthSource, Role, RoleName, User
from app.services.ldap_auth import authenticate_ldap_user


def _resolve_role(role_name: str) -> Role:
    role = Role.query.filter_by(name=role_name).first()
    if role:
        return role

    fallback = Role.query.filter_by(name=RoleName.VIEWER.value).first()
    if fallback:
        return fallback

    fallback = Role(name=RoleName.VIEWER.value)
    db.session.add(fallback)
    db.session.flush()
    return fallback


def _authenticate_local(username: str, password: str) -> User | None:
    user = User.query.filter_by(username=username, is_active=True).first()
    if user is None or user.is_locked() or not user.check_password(password):
        if user:
            user.record_failed_login()
            db.session.commit()
        return None
    return user


def _authenticate_ldap(username: str, password: str) -> User | None:
    local_admin_username = current_app.config["LDAP_LOCAL_ADMIN_USERNAME"]
    if username == local_admin_username:
        return _authenticate_local(username, password)

    ldap_user = authenticate_ldap_user(username, password)
    if ldap_user is None:
        return None

    user = User.query.filter_by(username=ldap_user.username).first()
    if user is None:
        role = _resolve_role(current_app.config["LDAP_DEFAULT_ROLE"])
        user = User(
            username=ldap_user.username,
            full_name=ldap_user.full_name,
            role_id=role.id,
            auth_source=AuthSource.LDAP.value,
            is_active=True,
        )
        db.session.add(user)
    else:
        user.full_name = ldap_user.full_name
        if not user.is_active:
            return None

    user.reset_failed_login()
    db.session.commit()
    return user


def register_routes(bp):
    @bp.post("/login")
    def login():
        payload = get_json()
        username = payload.get("username", "").strip()
        password = payload.get("password", "")

        if current_app.config["LDAP_ENABLED"]:
            user = _authenticate_ldap(username, password)
        else:
            user = _authenticate_local(username, password)

        if user is None:
            return api_response(message="Invalid credentials", status=401)

        user.reset_failed_login()
        db.session.commit()
        login_user(user)
        session.permanent = True
        return api_response(user_to_dict(user))

    @bp.post("/logout")
    @login_required
    def logout():
        logout_user()
        return api_response(message="Logged out")

    @bp.get("/me")
    @login_required
    def me():
        from flask_login import current_user

        return api_response(user_to_dict(current_user))
