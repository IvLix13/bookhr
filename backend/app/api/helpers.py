"""API helpers."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import jsonify, request
from flask_login import current_user, login_required

from app.models import RoleName

F = TypeVar("F", bound=Callable[..., Any])


def api_response(data: Any = None, status: int = 200, message: str | None = None):
    payload: dict[str, Any] = {"success": status < 400}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def require_roles(*roles: RoleName) -> Callable[[F], F]:
    def decorator(fn: F) -> F:
        @wraps(fn)
        @login_required
        def wrapper(*args: Any, **kwargs: Any):
            if not current_user.has_role(*roles):
                return api_response(message="Forbidden", status=403)
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def get_json() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def paginate_query(query, schema_fn, page: int = 1, per_page: int = 50):
    page = max(page, 1)
    per_page = min(max(per_page, 1), 200)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [schema_fn(item) for item in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }
