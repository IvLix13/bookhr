"""API helpers."""

from __future__ import annotations

from functools import wraps
from math import ceil
from typing import Any, Callable, TypeVar

from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import exists
from sqlalchemy.orm import Query
from sqlalchemy.sql.elements import ColumnElement

from app.models import Employment, Person, PersonNameHistory, RoleName

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


def load_schema(schema_class: type, data: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema_class()
    return schema.load(data if data is not None else get_json())


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


def join_current_person_name(query: Query[Any]) -> Query[Any]:
    """Join the current (valid_to IS NULL) person name for sorting/filtering.

    Does not apply DISTINCT. Current name is 1:1 with person, so joins stay
    row-preserving. Prefer this over SELECT DISTINCT + ORDER BY full_name —
    PostgreSQL requires ORDER BY expressions to appear in the SELECT list.
    """
    return query.join(Person, Employment.person_id == Person.id).join(
        PersonNameHistory,
        (PersonNameHistory.person_id == Person.id) & (PersonNameHistory.valid_to.is_(None)),
    )


def apply_employment_name_search(query: Query[Any], q: str | None) -> Query[Any]:
    """Filter by current person name without JOIN+DISTINCT (PG-safe with ORDER BY)."""
    if not q:
        return query

    return query.filter(
        exists().where(
            PersonNameHistory.person_id == Employment.person_id,
            PersonNameHistory.valid_to.is_(None),
            PersonNameHistory.full_name.ilike(f"%{q}%"),
        )
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
