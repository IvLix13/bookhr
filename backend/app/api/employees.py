"""Employees API."""

from __future__ import annotations

from datetime import date
from typing import Any

from flask import request
from flask_login import login_required

from app.api.helpers import (
    api_response,
    apply_employment_name_search,
    apply_sort,
    load_schema,
    join_current_person_name,
    paginate_query,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.api.schemas import (
    CreateEmployeeSchema,
    DismissEmployeeSchema,
    RehireEmployeeSchema,
    UpdateEmployeeSchema,
)
from app.api.serializers import employment_to_dict
from app.extensions import db
from app.models import Employment, EmploymentStatus, PersonNameHistory, RoleName
from app.services.employees import (
    create_person_with_employment,
    delete_employment,
    dismiss_employment,
    get_current_grade,
    get_current_name,
    get_current_position,
    rehire_person,
    sync_active_contract,
    sync_actual_grade,
    sync_passport,
    update_person_name,
    update_position,
)
from app.services.events import refresh_overdue_events
from app.services.grades import resolve_unknown_education_snapshot
from app.services.rule_engine import recalculate_employment_events
from app.services.tenure import (
    MAX_EMPLOYMENT_PERIODS,
    count_employment_periods,
    ensure_tenure_awards,
)
from app.tenant import get_request_company_id
from app.utils.dates import today_moscow


def _parse_optional_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _payload_has(payload: dict[str, Any], key: str) -> bool:
    return key in payload


EMPLOYEE_SORT_FIELDS = {
    "hire_date": Employment.hire_date,
    "status": Employment.status,
    "full_name": PersonNameHistory.full_name,
}


def register_routes(bp):
    @bp.get("/employees")
    @login_required
    def list_employees():
        company_id = get_request_company_id()
        active_only = request.args.get("active_only", "true").lower() == "true"
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            EMPLOYEE_SORT_FIELDS,
            default_field="hire_date",
            default_direction="desc",
        )

        query = Employment.query.filter_by(company_id=company_id)
        if active_only:
            query = query.filter_by(status=EmploymentStatus.ACTIVE.value)

        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)

        query = apply_sort(query, EMPLOYEE_SORT_FIELDS, sort, direction)

        return api_response(paginate_query(query, employment_to_dict, page, per_page))

    @bp.post("/employees")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_employee():
        payload = load_schema(CreateEmployeeSchema)
        company_id = get_request_company_id()
        hire_date = payload["hire_date"]
        full_name = payload["full_name"].strip()

        person, employment = create_person_with_employment(
            company_id=company_id,
            full_name=full_name,
            hire_date=hire_date,
            title=(payload.get("title") or "Не указана").strip() or "Не указана",
            position_grade_id=payload.get("position_grade_id"),
            education_status=payload["education_status"],
        )
        ensure_tenure_awards(person.id, company_id)

        sync_active_contract(
            employment,
            payload.get("contract_end"),
            term_years=payload.get("contract_term_years"),
        )
        sync_actual_grade(
            employment,
            payload.get("actual_grade_id"),
            payload.get("grade_date"),
        )
        sync_passport(person, payload.get("passport_until"))
        db.session.flush()
        recalculate_employment_events(employment)
        refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(employment_to_dict(employment), status=201)

    @bp.patch("/employees/<int:employment_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_employee(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if not employment or employment.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)

        payload = load_schema(UpdateEmployeeSchema)
        effective_date = payload.get("effective_date") or today_moscow()
        needs_recalc = False

        if _payload_has(payload, "full_name"):
            full_name = (payload.get("full_name") or "").strip()
            if full_name != get_current_name(employment.person):
                update_person_name(employment.person, full_name, effective_date)
                needs_recalc = True

        if _payload_has(payload, "title") or _payload_has(payload, "position_grade_id"):
            current_position = get_current_position(employment)
            title = payload.get("title")
            if title is None:
                title = current_position.title if current_position else "Не указана"
            position_grade_id = (
                payload.get("position_grade_id")
                if _payload_has(payload, "position_grade_id")
                else (current_position.position_grade_id if current_position else None)
            )
            update_position(
                employment,
                str(title).strip() or "Не указана",
                position_grade_id,
                effective_date,
            )

        if _payload_has(payload, "education_status"):
            education_status = payload["education_status"]
            employment.person.education_status = education_status
            if resolve_unknown_education_snapshot(employment, education_status):
                needs_recalc = True

        if _payload_has(payload, "hire_date"):
            hire_date = payload.get("hire_date")
            if hire_date and hire_date != employment.hire_date:
                employment.hire_date = hire_date
                ensure_tenure_awards(employment.person_id, employment.company_id)
                needs_recalc = True

        if _payload_has(payload, "contract_end") or _payload_has(payload, "contract_term_years"):
            sync_active_contract(
                employment,
                payload.get("contract_end"),
                term_years=payload.get("contract_term_years"),
            )
            needs_recalc = True

        if _payload_has(payload, "actual_grade_id") or _payload_has(payload, "grade_date"):
            current_grade = get_current_grade(employment)
            grade_id = (
                payload.get("actual_grade_id")
                if _payload_has(payload, "actual_grade_id")
                else (current_grade.grade_id if current_grade else None)
            )
            grade_date = (
                payload.get("grade_date")
                if _payload_has(payload, "grade_date")
                else (current_grade.assigned_date if current_grade else None)
            )
            sync_actual_grade(employment, grade_id, grade_date)
            needs_recalc = True

        if _payload_has(payload, "passport_until"):
            sync_passport(
                employment.person,
                payload.get("passport_until"),
            )
            needs_recalc = True

        db.session.flush()
        if needs_recalc:
            recalculate_employment_events(employment)
            refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(employment_to_dict(employment))

    @bp.delete("/employees/<int:employment_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def delete_employee(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if not employment or employment.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)

        delete_employment(employment)
        db.session.commit()
        return api_response(message="Deleted")

    @bp.post("/employees/<int:employment_id>/dismiss")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def dismiss(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if not employment or employment.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)

        payload = load_schema(DismissEmployeeSchema)
        dismiss_employment(
            employment,
            payload.get("dismissal_date") or today_moscow(),
            payload.get("reason"),
        )
        recalculate_employment_events(employment)
        refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(employment_to_dict(employment))

    @bp.post("/employees/<int:person_id>/rehire")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def rehire(person_id: int):
        from app.models import Person

        person = db.session.get(Person, person_id)
        if not person:
            return api_response(message="Not found", status=404)

        payload = load_schema(RehireEmployeeSchema)
        hire_date = payload["hire_date"]
        company_id = get_request_company_id()
        periods = count_employment_periods(person_id, company_id)
        if periods >= MAX_EMPLOYMENT_PERIODS:
            return api_response(
                message="Достигнут лимит периодов работы (не более 3)",
                status=400,
            )

        employment = rehire_person(
            person,
            company_id,
            hire_date,
            payload.get("title", "Не указана"),
            payload.get("position_grade_id"),
        )
        ensure_tenure_awards(person.id, company_id)
        sync_active_contract(
            employment,
            payload.get("contract_end"),
            term_years=payload.get("contract_term_years"),
        )
        sync_actual_grade(
            employment,
            payload.get("actual_grade_id"),
            payload.get("grade_date"),
        )
        sync_passport(person, payload.get("passport_until"))
        db.session.flush()
        recalculate_employment_events(employment)
        refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(employment_to_dict(employment), status=201)
