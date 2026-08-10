"""Employees API."""

from __future__ import annotations

from datetime import date
from typing import Any

from flask import request
from flask_login import login_required

from app.api.helpers import api_response, get_json, paginate_query, require_roles
from app.api.serializers import employment_to_dict
from app.extensions import db
from app.models import Employment, EmploymentStatus, RoleName
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
from app.services.rule_engine import recalculate_employment_events
from app.services.tenure import ensure_tenure_awards
from app.utils.dates import today_moscow


def _parse_optional_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _payload_has(payload: dict[str, Any], key: str) -> bool:
    return key in payload


def register_routes(bp):
    @bp.get("/employees")
    @login_required
    def list_employees():
        company_id = request.args.get("company_id", type=int, default=1)
        active_only = request.args.get("active_only", "true").lower() == "true"
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        query = Employment.query.filter_by(company_id=company_id)
        if active_only:
            query = query.filter_by(status=EmploymentStatus.ACTIVE.value)
        query = query.order_by(Employment.hire_date.desc())

        return api_response(paginate_query(query, employment_to_dict, page, per_page))

    @bp.post("/employees")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_employee():
        payload = get_json()
        company_id = payload.get("company_id", 1)
        hire_date = _parse_optional_date(payload.get("hire_date"))
        full_name = (payload.get("full_name") or "").strip()
        if not full_name or not hire_date:
            return api_response(message="full_name and hire_date are required", status=400)

        person, employment = create_person_with_employment(
            company_id=company_id,
            full_name=full_name,
            hire_date=hire_date,
            title=(payload.get("title") or "Не указана").strip() or "Не указана",
            position_grade_id=payload.get("position_grade_id"),
            has_university=bool(payload.get("has_university", False)),
        )
        ensure_tenure_awards(employment.id, hire_date)

        sync_active_contract(
            employment,
            _parse_optional_date(payload.get("contract_end")),
            start_date=hire_date,
        )
        sync_actual_grade(
            employment,
            payload.get("actual_grade_id"),
            _parse_optional_date(payload.get("grade_date")),
        )
        sync_passport(person, _parse_optional_date(payload.get("passport_until")))
        db.session.flush()
        recalculate_employment_events(employment)
        refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(employment_to_dict(employment), status=201)

    @bp.patch("/employees/<int:employment_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_employee(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if not employment:
            return api_response(message="Not found", status=404)

        payload = get_json()
        effective_date = _parse_optional_date(
            payload.get("effective_date", today_moscow().isoformat())
        ) or today_moscow()
        needs_recalc = False

        if _payload_has(payload, "full_name"):
            full_name = (payload.get("full_name") or "").strip()
            if not full_name:
                return api_response(message="full_name cannot be empty", status=400)
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

        if _payload_has(payload, "has_university"):
            employment.person.has_university = bool(payload.get("has_university"))

        if _payload_has(payload, "hire_date"):
            hire_date = _parse_optional_date(payload.get("hire_date"))
            if not hire_date:
                return api_response(message="hire_date cannot be empty", status=400)
            if hire_date != employment.hire_date:
                employment.hire_date = hire_date
                ensure_tenure_awards(employment.id, hire_date)
                needs_recalc = True

        if _payload_has(payload, "contract_end"):
            sync_active_contract(
                employment,
                _parse_optional_date(payload.get("contract_end")),
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
                _parse_optional_date(payload.get("grade_date"))
                if _payload_has(payload, "grade_date")
                else (current_grade.assigned_date if current_grade else None)
            )
            sync_actual_grade(employment, grade_id, grade_date)
            needs_recalc = True

        if _payload_has(payload, "passport_until"):
            sync_passport(
                employment.person,
                _parse_optional_date(payload.get("passport_until")),
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
        if not employment:
            return api_response(message="Not found", status=404)

        delete_employment(employment)
        db.session.commit()
        return api_response(message="Deleted")

    @bp.post("/employees/<int:employment_id>/dismiss")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def dismiss(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if not employment:
            return api_response(message="Not found", status=404)

        payload = get_json()
        dismiss_employment(
            employment,
            _parse_optional_date(payload.get("dismissal_date")) or today_moscow(),
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

        payload = get_json()
        hire_date = _parse_optional_date(payload.get("hire_date"))
        if not hire_date:
            return api_response(message="hire_date is required", status=400)

        employment = rehire_person(
            person,
            payload.get("company_id", 1),
            hire_date,
            payload.get("title", "Не указана"),
            payload.get("position_grade_id"),
        )
        ensure_tenure_awards(employment.id, hire_date)
        sync_active_contract(
            employment,
            _parse_optional_date(payload.get("contract_end")),
            start_date=hire_date,
        )
        sync_actual_grade(
            employment,
            payload.get("actual_grade_id"),
            _parse_optional_date(payload.get("grade_date")),
        )
        sync_passport(person, _parse_optional_date(payload.get("passport_until")))
        db.session.flush()
        recalculate_employment_events(employment)
        refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(employment_to_dict(employment), status=201)
