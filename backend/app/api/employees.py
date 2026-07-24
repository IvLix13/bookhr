"""Employees API."""

from __future__ import annotations

from datetime import date

from flask import request
from flask_login import login_required

from app.api.helpers import api_response, get_json, paginate_query, require_roles
from app.api.serializers import employment_to_dict
from app.extensions import db
from app.models import Employment, EmploymentStatus, RoleName
from app.services.employees import (
    create_person_with_employment,
    dismiss_employment,
    rehire_person,
    update_person_name,
    update_position,
)
from app.services.tenure import ensure_tenure_awards


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
        hire_date = date.fromisoformat(payload["hire_date"])

        person, employment = create_person_with_employment(
            company_id=company_id,
            full_name=payload["full_name"],
            hire_date=hire_date,
            title=payload.get("title", "Не указана"),
            position_grade_id=payload.get("position_grade_id"),
            has_university=payload.get("has_university", False),
        )
        ensure_tenure_awards(employment.id, hire_date)
        db.session.commit()
        return api_response(employment_to_dict(employment), status=201)

    @bp.patch("/employees/<int:employment_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_employee(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if not employment:
            return api_response(message="Not found", status=404)

        payload = get_json()
        effective_date = date.fromisoformat(
            payload.get("effective_date", date.today().isoformat())
        )

        if "full_name" in payload:
            update_person_name(employment.person, payload["full_name"], effective_date)
        if "title" in payload:
            update_position(
                employment,
                payload["title"],
                payload.get("position_grade_id"),
                effective_date,
            )
        if "has_university" in payload:
            employment.person.has_university = payload["has_university"]

        db.session.commit()
        return api_response(employment_to_dict(employment))

    @bp.post("/employees/<int:employment_id>/dismiss")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def dismiss(employment_id: int):
        employment = db.session.get(Employment, employment_id)
        if not employment:
            return api_response(message="Not found", status=404)

        payload = get_json()
        dismiss_employment(
            employment,
            date.fromisoformat(payload["dismissal_date"]),
            payload.get("reason"),
        )
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
        hire_date = date.fromisoformat(payload["hire_date"])
        employment = rehire_person(
            person,
            payload.get("company_id", 1),
            hire_date,
            payload.get("title", "Не указана"),
            payload.get("position_grade_id"),
        )
        ensure_tenure_awards(employment.id, hire_date)
        db.session.commit()
        return api_response(employment_to_dict(employment), status=201)
