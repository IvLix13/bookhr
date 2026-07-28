"""Dashboard stats API."""

from __future__ import annotations

from datetime import date

from flask import request
from flask_login import login_required

from app.api.helpers import api_response
from app.services.statistics import build_dashboard_stats


def register_routes(bp):
    @bp.get("/stats")
    @login_required
    def stats():
        company_id = request.args.get("company_id", 1, type=int)
        date_from_raw = request.args.get("from")
        date_to_raw = request.args.get("to")
        date_from = date.fromisoformat(date_from_raw) if date_from_raw else None
        date_to = date.fromisoformat(date_to_raw) if date_to_raw else None
        return api_response(build_dashboard_stats(company_id, date_from, date_to))
