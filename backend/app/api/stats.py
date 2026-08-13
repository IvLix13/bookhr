"""Dashboard stats API."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import api_response
from app.api.schemas import parse_query_date
from app.services.statistics import build_dashboard_stats
from app.tenant import get_request_company_id


def register_routes(bp):
    @bp.get("/stats")
    @login_required
    def stats():
        company_id = get_request_company_id()
        date_from = parse_query_date(request.args.get("from"), field_name="from")
        date_to = parse_query_date(request.args.get("to"), field_name="to")
        return api_response(build_dashboard_stats(company_id, date_from, date_to))
