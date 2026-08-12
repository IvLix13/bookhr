"""Admin user management API."""

from __future__ import annotations

from flask import request
from flask_login import current_user
from sqlalchemy import or_

from app.api.helpers import (
    api_response,
    apply_sort,
    paginate_query,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.api.serializers import role_to_dict, user_admin_to_dict
from app.extensions import db
from app.models import Role, RoleName, User
from app.services.users import create_local_user, reset_user_password, unlock_user, update_user


USER_SORT_FIELDS = {
    "username": User.username,
    "full_name": User.full_name,
    "role": Role.name,
}


def register_routes(bp):
    @bp.get("/roles")
    @require_roles(RoleName.ADMIN)
    def list_roles():
        roles = Role.query.order_by(Role.name.asc()).all()
        return api_response([role_to_dict(role) for role in roles])

    @bp.get("/users")
    @require_roles(RoleName.ADMIN)
    def list_users():
        page, per_page = parse_pagination_args()
        q = parse_search_q(min_length=1)
        sort, direction = parse_sort_args(
            USER_SORT_FIELDS,
            default_field="username",
            default_direction="asc",
        )
        role = request.args.get("role", type=str)
        auth_source = request.args.get("auth_source", type=str)
        is_active = request.args.get("is_active", type=str)

        query = User.query.join(Role, User.role_id == Role.id)
        if q:
            pattern = f"%{q}%"
            query = query.filter(or_(User.username.ilike(pattern), User.full_name.ilike(pattern)))
        if role:
            query = query.filter(Role.name == role)
        if auth_source:
            query = query.filter(User.auth_source == auth_source)
        if is_active is not None and is_active != "":
            query = query.filter(User.is_active.is_(is_active.lower() == "true"))

        query = apply_sort(query, USER_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, user_admin_to_dict, page, per_page))

    @bp.post("/users")
    @require_roles(RoleName.ADMIN)
    def create_user_route():
        from app.api.helpers import get_json

        payload = get_json()
        try:
            user = create_local_user(
                username=payload.get("username", ""),
                password=payload.get("password", ""),
                full_name=payload.get("full_name", ""),
                role_name=payload.get("role", RoleName.VIEWER.value),
                actor=current_user,
            )
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            return api_response(message=str(exc), status=400)
        return api_response(user_admin_to_dict(user), status=201)

    @bp.patch("/users/<int:user_id>")
    @require_roles(RoleName.ADMIN)
    def update_user_route(user_id: int):
        from app.api.helpers import get_json

        user = db.session.get(User, user_id)
        if not user:
            return api_response(message="Not found", status=404)

        payload = get_json()
        try:
            update_user(
                user,
                actor=current_user,
                full_name=payload.get("full_name") if "full_name" in payload else None,
                role_name=payload.get("role") if "role" in payload else None,
                is_active=payload.get("is_active") if "is_active" in payload else None,
            )
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            return api_response(message=str(exc), status=400)
        return api_response(user_admin_to_dict(user))

    @bp.post("/users/<int:user_id>/unlock")
    @require_roles(RoleName.ADMIN)
    def unlock_user_route(user_id: int):
        user = db.session.get(User, user_id)
        if not user:
            return api_response(message="Not found", status=404)
        try:
            unlock_user(user, actor=current_user)
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            return api_response(message=str(exc), status=400)
        return api_response(user_admin_to_dict(user))

    @bp.post("/users/<int:user_id>/reset-password")
    @require_roles(RoleName.ADMIN)
    def reset_password_route(user_id: int):
        from app.api.helpers import get_json

        user = db.session.get(User, user_id)
        if not user:
            return api_response(message="Not found", status=404)

        payload = get_json()
        try:
            reset_user_password(
                user,
                password=payload.get("password", ""),
                actor=current_user,
            )
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            return api_response(message=str(exc), status=400)
        return api_response(user_admin_to_dict(user))
