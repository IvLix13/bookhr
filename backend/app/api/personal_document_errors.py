"""Personal-document errors for HR and administrators of the configured company."""

from datetime import UTC
from zoneinfo import ZoneInfo

from flask import current_app, send_file
from sqlalchemy.exc import SQLAlchemyError

from app.api.helpers import api_response, require_roles
from app.extensions import db
from app.models import PersonalDocumentErrorsSnapshot, RoleName
from app.services.personal_document_errors import (
    build_personal_document_errors_workbook,
    configured_base_url,
    personal_file_url,
    refresh_snapshot,
)
from app.tenant import get_request_company_id


def _company_allowed(company_id: int) -> bool:
    configured_company_id = current_app.config["PERSONAL_DOCUMENT_ERRORS_COMPANY_ID"]
    return configured_company_id <= 0 or company_id == configured_company_id


def register_routes(bp):
    @bp.post("/personal-document-errors/refresh")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def refresh_personal_document_errors():
        company_id = get_request_company_id()
        config = current_app.config
        if not _company_allowed(company_id):
            return api_response(message="Forbidden", status=403)

        last_success_at = None
        items = []
        base_url = configured_base_url()
        state = "not_configured"
        if base_url:
            try:
                snapshot, refreshing = refresh_snapshot(company_id)
            except SQLAlchemyError as error:
                # Database exceptions can include the bound JSON snapshot.
                current_app.logger.error("Personal document errors snapshot unavailable (%s)", type(error).__name__)
                return api_response(message="Не удалось загрузить список ошибок.", status=503)
            state = "refreshing" if refreshing else "source_error"
            if snapshot is not None:
                if not refreshing and snapshot["last_attempt_succeeded"]:
                    state = "ready"
                success_at = snapshot["last_success_at"]
                if success_at is not None:
                    if success_at.tzinfo is None:
                        success_at = success_at.replace(tzinfo=UTC)
                    last_success_at = success_at.astimezone(ZoneInfo(config["TIMEZONE"])).isoformat()
                items = [
                    {**card, "personal_file_url": personal_file_url(base_url, card["ldnumber"])}
                    for card in snapshot["items"]
                ]

        response, status = api_response({
            "state": state,
            "last_success_at": last_success_at,
            "timezone": config["TIMEZONE"],
            "items": items,
        })
        response.cache_control.no_store = True
        return response, status

    @bp.get("/personal-document-errors/export")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def export_personal_document_errors():
        company_id = get_request_company_id()
        if not _company_allowed(company_id):
            return api_response(message="Forbidden", status=403)

        base_url = configured_base_url()
        if not base_url:
            return api_response(message="Источник ошибок в ЛД не настроен.", status=404)

        snapshot = db.session.get(PersonalDocumentErrorsSnapshot, company_id)
        if snapshot is None or snapshot.last_success_at is None:
            return api_response(message="Список ошибок в ЛД ещё не загружен.", status=404)

        response = send_file(
            build_personal_document_errors_workbook(snapshot.items, base_url),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="personal_document_errors.xlsx",
        )
        response.cache_control.no_store = True
        return response
