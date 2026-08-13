"""CSRF protection for SPA session auth."""

from __future__ import annotations

import secrets

from flask import abort, request, session

CSRF_HEADER = "X-CSRF-Token"
CSRF_SESSION_KEY = "csrf_token"

CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/login",
        "/api/csrf",
    }
)


def get_or_create_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_hex(32)
        session[CSRF_SESSION_KEY] = token
    return token


def rotate_csrf_token() -> str:
    token = secrets.token_hex(32)
    session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf() -> None:
    from flask import current_app

    if current_app.config.get("TESTING"):
        return
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not request.path.startswith("/api/"):
        return
    if request.path in CSRF_EXEMPT_PATHS:
        return

    expected = session.get(CSRF_SESSION_KEY)
    provided = request.headers.get(CSRF_HEADER)
    if not expected or not provided or provided != expected:
        abort(403)
