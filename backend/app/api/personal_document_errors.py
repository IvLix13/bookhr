"""Personal-document errors for HR and administrators of the configured company."""

from datetime import UTC
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.api.helpers import api_response, require_roles
from app.models import RoleName
from app.services.personal_document_errors import configured_base_url, refresh_snapshot
from app.tenant import get_request_company_id


def register_routes(bp):
    @bp.post("/personal-document-errors/refresh")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def refresh_personal_document_errors():
        company_id = get_request_company_id()
        config = current_app.config
        configured_company_id = config["PERSONAL_DOCUMENT_ERRORS_COMPANY_ID"]
        if configured_company_id > 0 and company_id != configured_company_id:
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
                    {**card, "personal_file_url": f"{base_url}/personalfile/{quote(card['ldnumber'], safe='')}"}
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
