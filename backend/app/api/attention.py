"""Attention summary API."""

from __future__ import annotations

from flask import request
from app.api.helpers import api_response, require_roles
from app.models import RoleName
from app.services.attention import ALL_CATEGORIES, build_attention_summary
from app.tenant import get_request_company_id


def register_routes(bp):
    @bp.get("/attention")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def attention():
        company_id = get_request_company_id()
        limit = request.args.get("limit", 10, type=int)
        categories_raw = request.args.get("categories")
        categories = None
        if categories_raw:
            categories = [
                value.strip()
                for value in categories_raw.split(",")
                if value.strip() in ALL_CATEGORIES
            ]

        return api_response(build_attention_summary(company_id, limit, categories))
