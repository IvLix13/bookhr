"""Authentication API."""

from __future__ import annotations

from flask import session
from flask_login import login_required, login_user, logout_user

from app.api.helpers import api_response, get_json
from app.api.serializers import user_to_dict
from app.extensions import db
from app.models import User


def register_routes(bp):
    @bp.post("/login")
    def login():
        payload = get_json()
        username = payload.get("username", "").strip()
        password = payload.get("password", "")

        user = User.query.filter_by(username=username, is_active=True).first()
        if user is None or user.is_locked() or not user.check_password(password):
            if user:
                user.record_failed_login()
                db.session.commit()
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
