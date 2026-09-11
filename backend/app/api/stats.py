"""Dashboard and manual statistics API."""

from __future__ import annotations

from flask import request, send_file
from flask_login import login_required

from app.api.helpers import api_response, require_roles
from app.api.schemas import parse_query_date
from app.extensions import db
from app.models import ManualStatisticsSnapshot, RoleName
from app.services.manual_statistics import (
    build_manual_statistics_template,
    manual_statistics_to_dict,
    parse_manual_statistics_workbook,
    save_manual_statistics,
)
from app.services.statistics import build_dashboard_stats
from app.tenant import get_request_company_id


MANUAL_STATS_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def register_routes(bp):
    @bp.get("/stats")
    @login_required
    def stats():
        company_id = get_request_company_id()
        date_from = parse_query_date(request.args.get("from"), field_name="from")
        date_to = parse_query_date(request.args.get("to"), field_name="to")
        return api_response(build_dashboard_stats(company_id, date_from, date_to))

    @bp.get("/stats/manual")
    @login_required
    def manual_stats():
        company_id = get_request_company_id()
        snapshot = ManualStatisticsSnapshot.query.filter_by(company_id=company_id).first()
        return api_response(manual_statistics_to_dict(snapshot))

    @bp.post("/stats/manual/upload")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def upload_manual_stats():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return api_response(message="Выберите Excel-файл", status=400)
        if not uploaded.filename.lower().endswith(".xlsx"):
            return api_response(message="Поддерживается только формат .xlsx", status=400)

        try:
            items = parse_manual_statistics_workbook(uploaded.stream)
        except ValueError as exc:
            return api_response(message=str(exc), status=400)

        snapshot = save_manual_statistics(
            get_request_company_id(),
            items,
            uploaded.filename,
        )
        db.session.commit()
        return api_response(manual_statistics_to_dict(snapshot))

    @bp.get("/stats/manual/template")
    @login_required
    def manual_stats_template():
        return send_file(
            build_manual_statistics_template(),
            mimetype=MANUAL_STATS_MIME,
            as_attachment=True,
            download_name="manual_statistics_template.xlsx",
        )
