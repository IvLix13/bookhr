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
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.extensions import db
from app.models import (
    Employment,
    EmploymentStatus,
    Event,
    EventType,
    PersonNameHistory,
    RoleName,
)
from app.services.attestations import (
    attestation_rule_keys,
    find_attestation_events,
    preparation_date,
    set_attestation_date,
)
from app.services.events import effective_event_status
from app.services.employees import get_current_name
from app.tenant import get_request_company_id

ATTESTATION_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "attestation_date": Employment.attestation_date,
    "attestation_preparation_date": Employment.attestation_date,
}


def attestation_row_to_dict(employment: Employment, event: Event | None = None) -> dict:
    prep_date = preparation_date(employment.attestation_date)
    current_event = event if employment.attestation_date else None
    return {
        "employment_id": employment.id,
        "full_name": get_current_name(employment.person),
        "attestation_date": (
            employment.attestation_date.isoformat()
            if employment.attestation_date
            else None
        ),
        "attestation_preparation_date": prep_date.isoformat() if prep_date else None,
        "attestation_event_id": current_event.id if current_event else None,
        "attestation_status": (
            effective_event_status(current_event) if current_event else None
        ),
    }


def register_routes(bp):
    @bp.get("/attestations/<int:employment_id>")
    @login_required
    def get_attestation(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if (
            not employment
            or employment.company_id != get_request_company_id()
            or not employment.is_active
        ):
            return api_response(message="Not found", status=404)
        event = find_attestation_events(employment).get(EventType.ATTESTATION.value)
        return api_response(attestation_row_to_dict(employment, event))

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
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        ids = [employment.id for employment in pagination.items]
        keys = [
            attestation_rule_keys(employment)[EventType.ATTESTATION.value]
            for employment in pagination.items
        ]
        events = (
            Event.query.filter(
                Event.company_id == company_id,
                Event.employment_id.in_(ids),
                Event.event_type == EventType.ATTESTATION.value,
                Event.source == "rule",
                Event.reference_type == "employment",
                Event.reference_id == Event.employment_id,
                Event.rule_key.in_(keys),
            ).all()
            if ids
            else []
        )
        by_employment = {event.employment_id: event for event in events}
        items = []
        for employment in pagination.items:
            event = by_employment.get(employment.id)
            if (
                event
                and event.rule_key
                != attestation_rule_keys(employment)[EventType.ATTESTATION.value]
            ):
                event = None
            items.append(attestation_row_to_dict(employment, event))
        return api_response(
            {
                "items": items,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            }
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
            new_date = None
        else:
            try:
                new_date = date.fromisoformat(str(raw_date))
            except ValueError:
                return api_response(
                    message="attestation_date must be ISO date",
                    status=400,
                )

        try:
            set_attestation_date(employment, new_date)
        except ValueError as exc:
            db.session.rollback()
            return api_response(message=str(exc), status=400)
        db.session.commit()
        event = find_attestation_events(employment).get(EventType.ATTESTATION.value)
        return api_response(attestation_row_to_dict(employment, event))
