"""Domain module APIs: contracts, grades, passports, tenure, grade catalog."""

from __future__ import annotations

from datetime import date

from flask import request
from flask_login import login_required

from app.api.helpers import api_response, get_json, require_roles
from app.api.serializers import (
    contract_to_dict,
    grade_row_to_dict,
    grade_to_dict,
    passport_row_to_dict,
    tenure_row_to_dict,
)
from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    EmploymentStatus,
    GradeCatalog,
    Passport,
    RoleName,
)
from app.services.employees import get_active_passport
from app.services.tenure import ensure_tenure_awards


def register_routes(bp):
    @bp.get("/contracts")
    @login_required
    def list_contracts():
        company_id = request.args.get("company_id", 1, type=int)
        employments = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        ).all()
        contracts = []
        for employment in employments:
            for contract in employment.contracts:
                if contract.is_active:
                    contracts.append(contract_to_dict(contract))
        contracts.sort(key=lambda item: item["days_left"])
        return api_response(contracts)

    @bp.post("/contracts")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_contract():
        payload = get_json()
        contract = Contract(
            employment_id=payload["employment_id"],
            start_date=date.fromisoformat(payload["start_date"]),
            end_date=date.fromisoformat(payload["end_date"]),
            notes=payload.get("notes"),
        )
        db.session.add(contract)
        db.session.commit()
        return api_response(contract_to_dict(contract), status=201)

    @bp.get("/grades")
    @login_required
    def list_grades():
        company_id = request.args.get("company_id", 1, type=int)
        employments = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        ).all()
        return api_response([grade_row_to_dict(e) for e in employments])

    @bp.get("/grade-catalog")
    @login_required
    def list_grade_catalog():
        grades = GradeCatalog.query.order_by(GradeCatalog.rank.asc()).all()
        return api_response([grade_to_dict(g) for g in grades])

    @bp.post("/grade-catalog")
    @require_roles(RoleName.ADMIN)
    def create_grade():
        payload = get_json()
        grade = GradeCatalog(
            name=payload["name"],
            rank=payload["rank"],
            min_months=payload.get("min_months", 12),
        )
        db.session.add(grade)
        db.session.commit()
        return api_response(grade_to_dict(grade), status=201)

    @bp.patch("/grade-catalog/<int:grade_id>")
    @require_roles(RoleName.ADMIN)
    def update_grade(grade_id: int):
        grade = db.session.get(GradeCatalog, grade_id)
        if not grade:
            return api_response(message="Not found", status=404)
        payload = get_json()
        for field in ("name", "rank", "min_months", "is_active"):
            if field in payload:
                setattr(grade, field, payload[field])
        db.session.commit()
        return api_response(grade_to_dict(grade))

    @bp.post("/grades/assign")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def assign_grade():
        payload = get_json()
        employment = db.session.get(Employment, payload["employment_id"])
        if not employment:
            return api_response(message="Not found", status=404)

        current = (
            EmployeeGradeHistory.query.filter_by(
                employment_id=employment.id,
                valid_to=None,
            ).first()
        )
        assigned_date = date.fromisoformat(payload["assigned_date"])
        if current:
            current.valid_to = assigned_date

        history = EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=payload["grade_id"],
            assigned_date=assigned_date,
            basis=payload.get("basis"),
        )
        db.session.add(history)
        db.session.commit()
        return api_response(grade_row_to_dict(employment))

    @bp.get("/passports")
    @login_required
    def list_passports():
        company_id = request.args.get("company_id", 1, type=int)
        employments = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        ).all()
        rows = [passport_row_to_dict(e.person, e) for e in employments]
        rows.sort(key=lambda item: item.get("days_left") or 99999)
        return api_response(rows)

    @bp.post("/passports")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_passport():
        payload = get_json()
        from app.models import Person

        person = db.session.get(Person, payload["person_id"])
        if not person:
            return api_response(message="Not found", status=404)

        active = get_active_passport(person)
        if active:
            active.is_active = False

        passport = Passport(
            person_id=person.id,
            valid_until=date.fromisoformat(payload["valid_until"]),
            series_number=payload.get("series_number"),
        )
        db.session.add(passport)
        db.session.commit()

        employment = Employment.query.filter_by(person_id=person.id).first()
        return api_response(passport_row_to_dict(person, employment), status=201)

    @bp.get("/tenure")
    @login_required
    def list_tenure():
        company_id = request.args.get("company_id", 1, type=int)
        employments = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        ).all()
        for employment in employments:
            ensure_tenure_awards(employment.id, employment.hire_date)
        db.session.commit()
        return api_response([tenure_row_to_dict(e) for e in employments])

    @bp.patch("/tenure/<int:award_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_tenure_award(award_id: int):
        from app.models import TenureAward

        award = db.session.get(TenureAward, award_id)
        if not award:
            return api_response(message="Not found", status=404)
        payload = get_json()
        award.is_received = payload.get("is_received", award.is_received)
        if payload.get("received_date"):
            award.received_date = date.fromisoformat(payload["received_date"])
        db.session.commit()
        return api_response({"id": award.id, "is_received": award.is_received})
