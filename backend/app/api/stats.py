"""Dashboard stats API (basic MVP)."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import api_response
from app.models import EmployeeGradeHistory, Event, EventStatus, TenureAward


def register_routes(bp):
    @bp.get("/stats")
    @login_required
    def stats():
        company_id = request.args.get("company_id", 1, type=int)
        return api_response(
            {
                "completed_events": Event.query.filter_by(
                    company_id=company_id,
                    status=EventStatus.COMPLETED.value,
                ).count(),
                "planned_events": Event.query.filter_by(
                    company_id=company_id,
                    status=EventStatus.PLANNED.value,
                ).count(),
                "grades_assigned": EmployeeGradeHistory.query.count(),
                "awards_received": TenureAward.query.filter_by(is_received=True).count(),
            }
        )
