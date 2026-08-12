"""User administration helpers."""

from __future__ import annotations

import re

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AuthSource, Role, RoleName, User
from app.services.audit import log_audit
from app.services.password_policy import validate_password


_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,64}$")


def validate_username(username: str) -> str:
    value = username.strip()
    if not _USERNAME_RE.fullmatch(value):
        raise ValueError("username must be 3-64 chars: letters, digits, . _ -")
    return value


def resolve_role(role_name: str) -> Role:
    try:
        enum_value = RoleName(role_name)
    except ValueError as exc:
        raise ValueError("invalid role") from exc

    role = Role.query.filter_by(name=enum_value.value).first()
    if not role:
        raise ValueError("role not found")
    return role


def count_active_admins(*, exclude_id: int | None = None) -> int:
    query = (
        User.query.join(Role, User.role_id == Role.id)
        .filter(User.is_active.is_(True), Role.name == RoleName.ADMIN.value)
    )
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    return query.count()


def is_break_glass_user(user: User) -> bool:
    if not current_app.config.get("LDAP_ENABLED"):
        return False
    return user.username == current_app.config["LDAP_LOCAL_ADMIN_USERNAME"]


def _user_audit_snapshot(user: User) -> dict:
    return {
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role_name,
        "auth_source": user.auth_source,
        "is_active": user.is_active,
        "is_locked": user.is_locked(),
    }


def _ensure_not_last_admin(user: User) -> None:
    if user.has_role(RoleName.ADMIN) and count_active_admins(exclude_id=user.id) == 0:
        raise ValueError("cannot remove the last active admin")


def _ensure_actor_can_modify(actor: User, target: User, *, role_change: bool = False) -> None:
    if actor.id == target.id and not target.is_active:
        raise ValueError("cannot deactivate yourself")
    if actor.id == target.id and role_change and target.has_role(RoleName.ADMIN):
        _ensure_not_last_admin(target)
    if is_break_glass_user(target):
        if not target.is_active:
            raise ValueError("cannot deactivate break-glass admin")
        if role_change and not target.has_role(RoleName.ADMIN):
            raise ValueError("cannot change break-glass admin role")


def create_local_user(
    *,
    username: str,
    password: str,
    full_name: str,
    role_name: str,
    actor: User,
) -> User:
    del actor  # reserved for future permission checks
    normalized_username = validate_username(username)
    validate_password(password, normalized_username)
    full_name_value = full_name.strip()
    if not full_name_value:
        raise ValueError("full_name is required")

    role = resolve_role(role_name)
    user = User(
        username=normalized_username,
        full_name=full_name_value,
        role_id=role.id,
        auth_source=AuthSource.LOCAL.value,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("username must be unique") from exc

    log_audit(
        action="create",
        entity_type="user",
        entity_id=user.id,
        new_value=_user_audit_snapshot(user),
    )
    return user


def update_user(
    user: User,
    *,
    actor: User,
    full_name: str | None = None,
    role_name: str | None = None,
    is_active: bool | None = None,
) -> User:
    old_value = _user_audit_snapshot(user)
    role_change = False

    if full_name is not None:
        full_name_value = full_name.strip()
        if not full_name_value:
            raise ValueError("full_name is required")
        user.full_name = full_name_value

    if role_name is not None:
        role_change = True
        new_role = resolve_role(role_name)
        if user.has_role(RoleName.ADMIN) and new_role.name != RoleName.ADMIN.value:
            _ensure_not_last_admin(user)
        _ensure_actor_can_modify(actor, user, role_change=True)
        user.role_id = new_role.id

    if is_active is not None:
        if not is_active:
            if actor.id == user.id:
                raise ValueError("cannot deactivate yourself")
            if is_break_glass_user(user):
                raise ValueError("cannot deactivate break-glass admin")
            _ensure_not_last_admin(user)
            user.is_active = False
            user.reset_failed_login()
        else:
            user.is_active = True

    log_audit(
        action="update",
        entity_type="user",
        entity_id=user.id,
        old_value=old_value,
        new_value=_user_audit_snapshot(user),
    )
    return user


def unlock_user(user: User, *, actor: User) -> User:
    del actor
    old_value = _user_audit_snapshot(user)
    user.reset_failed_login()
    log_audit(
        action="unlock",
        entity_type="user",
        entity_id=user.id,
        old_value=old_value,
        new_value=_user_audit_snapshot(user),
    )
    return user


def reset_user_password(user: User, *, password: str, actor: User) -> User:
    del actor
    if user.auth_source != AuthSource.LOCAL.value:
        raise ValueError("password reset is only allowed for local users")
    validate_password(password, user.username)
    user.set_password(password)
    user.reset_failed_login()
    log_audit(
        action="reset_password",
        entity_type="user",
        entity_id=user.id,
        new_value={"password": "***"},
    )
    return user
