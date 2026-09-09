"""Attestation dates API."""

from __future__ import annotations

from datetime import date

from flask_login import login_required

from app.api.helpers import (
    api_response,
    apply_employment_name_search,
    apply_sort,
    get_json,
    join_current_person_name,
    paginate_query,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.extensions import db
from app.models import Employment, EmploymentStatus, PersonNameHistory, RoleName
from app.services.employees import get_current_name
from app.tenant import get_request_company_id


ATTESTATION_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "attestation_date": Employment.attestation_date,
}


def attestation_row_to_dict(employment: Employment) -> dict:
    return {
        "employment_id": employment.id,
        "full_name": get_current_name(employment.person),
        "attestation_date": (
            employment.attestation_date.isoformat() if employment.attestation_date else None
        ),
    }


def register_routes(bp):
    @bp.get("/attestations")
    @login_required
    def list_attestations():
        company_id = get_request_company_id()
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            ATTESTATION_SORT_FIELDS,
            default_field="full_name",
            default_direction="asc",
        )

        query = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        )
        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)
        query = apply_sort(query, ATTESTATION_SORT_FIELDS, sort, direction)
        return api_response(
            paginate_query(query, attestation_row_to_dict, page, per_page)
        )

    @bp.patch("/attestations/<int:employment_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_attestation(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if (
            not employment
            or employment.company_id != get_request_company_id()
            or employment.status != EmploymentStatus.ACTIVE.value
        ):
            return api_response(message="Not found", status=404)

        payload = get_json()
        if "attestation_date" not in payload:
            return api_response(message="attestation_date is required", status=400)

        raw_date = payload.get("attestation_date")
        if raw_date in (None, ""):
            employment.attestation_date = None
        else:
            try:
                employment.attestation_date = date.fromisoformat(str(raw_date))
            except ValueError:
                return api_response(
                    message="attestation_date must be ISO date",
                    status=400,
                )

        db.session.commit()
        return api_response(attestation_row_to_dict(employment))
