"""Audit logging service."""

from __future__ import annotations

from typing import Any

from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def _current_user_id() -> int | None:
    from flask import has_request_context

    if not has_request_context():
        return None
    try:
        if current_user.is_authenticated:
            return current_user.id
    except AttributeError:
        return None
    return None


def log_audit(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        user_id=_current_user_id(),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
    )
    db.session.add(entry)
