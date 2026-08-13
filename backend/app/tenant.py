"""Tenant / company scoping helpers."""

from __future__ import annotations

from flask_login import current_user


def get_request_company_id() -> int:
    """Resolve company scope from the authenticated user (ignore client input)."""
    if current_user.is_authenticated:
        company_id = getattr(current_user, "company_id", None)
        if company_id:
            return int(company_id)
    return 1
