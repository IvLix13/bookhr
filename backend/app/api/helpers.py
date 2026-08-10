"""API helpers."""

from __future__ import annotations

from functools import wraps
from math import ceil
from typing import Any, Callable, TypeVar

from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.orm import Query
from sqlalchemy.sql.elements import ColumnElement

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


def parse_pagination_args(default_page: int = 1, default_per_page: int = 50) -> tuple[int, int]:
    page = request.args.get("page", default_page, type=int)
    per_page = request.args.get("per_page", default_per_page, type=int)
    page = max(page, 1)
    per_page = min(max(per_page, 1), 200)
    return page, per_page


def parse_sort_args(
    allowed: dict[str, ColumnElement[Any]],
    *,
    default_field: str,
    default_direction: str = "asc",
) -> tuple[str, str]:
    sort = request.args.get("sort", default_field)
    direction = request.args.get("direction", default_direction).lower()
    if sort not in allowed:
        sort = default_field
    if direction not in ("asc", "desc"):
        direction = default_direction
    return sort, direction


def apply_sort(
    query: Query[Any],
    allowed: dict[str, ColumnElement[Any]],
    sort: str,
    direction: str,
) -> Query[Any]:
    column = allowed[sort]
    order = column.asc() if direction == "asc" else column.desc()
    return query.order_by(order)


def parse_search_q(*, min_length: int = 2) -> str | None:
    raw = request.args.get("q")
    if raw is None:
        return None
    q = raw.strip()
    if not q:
        return None
    if len(q) < min_length:
        return None
    return q


def apply_text_search(
    query: Query[Any],
    column: ColumnElement[Any],
    q: str | None,
) -> Query[Any]:
    if not q:
        return query
    return query.filter(column.ilike(f"%{q}%"))


def apply_employment_name_search(query: Query[Any], q: str | None) -> Query[Any]:
    if not q:
        return query

    from app.models import Employment, Person, PersonNameHistory

    return (
        query.join(Person, Employment.person_id == Person.id)
        .join(
            PersonNameHistory,
            (PersonNameHistory.person_id == Person.id)
            & (PersonNameHistory.valid_to.is_(None)),
        )
        .filter(PersonNameHistory.full_name.ilike(f"%{q}%"))
        .distinct()
    )


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


def paginate_sequence(items: list[Any], page: int = 1, per_page: int = 50) -> dict[str, Any]:
    page = max(page, 1)
    per_page = min(max(per_page, 1), 200)
    total = len(items)
    pages = ceil(total / per_page) if total else 0
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }
