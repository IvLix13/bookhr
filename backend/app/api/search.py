"""Global search API."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import api_response
from app.services.search import search_all


def register_routes(bp):
    @bp.get("/search")
    @login_required
    def search():
        company_id = request.args.get("company_id", 1, type=int)
        limit = request.args.get("limit", 20, type=int)
        q = request.args.get("q", "").strip()

        if len(q) < 2:
            return api_response(message="Query must be at least 2 characters", status=400)

        return api_response(search_all(company_id, q, limit))
