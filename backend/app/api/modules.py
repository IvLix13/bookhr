"""Domain module APIs: contracts, grades, passports, tenure, grade catalog."""

from __future__ import annotations

from datetime import date

from flask import request
from flask_login import current_user, login_required

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
    Person,
    PersonNameHistory,
    RoleName,
)
from app.services.employees import get_active_passport
from app.services.events import refresh_overdue_events
from app.services.grade_catalog import (
    apply_grade_catalog_payload,
    commit_grade_catalog,
    validate_min_years,
    validate_rank,
    validate_rank_continuity,
)
from app.services.rule_engine import recalculate_employment_events
from app.services.tenure import ensure_tenure_awards


CONTRACT_SORT_FIELDS = {
    "end_date": Contract.end_date,
    "start_date": Contract.start_date,
    "full_name": PersonNameHistory.full_name,
}

EMPLOYEE_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "hire_date": Employment.hire_date,
}

PASSPORT_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "valid_until": Passport.valid_until,
}


def register_routes(bp):
    @bp.get("/contracts")
    @login_required
    def list_contracts():
        company_id = request.args.get("company_id", 1, type=int)
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            CONTRACT_SORT_FIELDS,
            default_field="end_date",
            default_direction="asc",
        )

        query = (
            Contract.query.join(Employment)
            .filter(
                Employment.company_id == company_id,
                Employment.status == EmploymentStatus.ACTIVE.value,
                Contract.is_active.is_(True),
            )
        )
        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)

        query = apply_sort(query, CONTRACT_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, contract_to_dict, page, per_page))

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
        db.session.flush()
        employment = db.session.get(Employment, payload["employment_id"])
        if employment:
            recalculate_employment_events(employment)
            refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(contract_to_dict(contract), status=201)

    @bp.get("/grades")
    @login_required
    def list_grades():
        company_id = request.args.get("company_id", 1, type=int)
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            EMPLOYEE_SORT_FIELDS,
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

        query = apply_sort(query, EMPLOYEE_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, grade_row_to_dict, page, per_page))

    @bp.get("/grade-catalog")
    @login_required
    def list_grade_catalog():
        grades = GradeCatalog.query.order_by(GradeCatalog.rank.asc()).all()
        return api_response([grade_to_dict(g) for g in grades])

    @bp.post("/grade-catalog")
    @require_roles(RoleName.ADMIN)
    def create_grade():
        payload = get_json()
        try:
            name = str(payload.get("name", "")).strip()
            if not name:
                raise ValueError("name is required")
            rank = validate_rank(payload["rank"])
            validate_rank_continuity(rank=rank)
            min_years = validate_min_years(payload.get("min_years", 1))
            grade = GradeCatalog(name=name, rank=rank, min_years=min_years)
            db.session.add(grade)
            commit_grade_catalog()
        except ValueError as exc:
            return api_response(message=str(exc), status=400)
        return api_response(grade_to_dict(grade), status=201)

    @bp.patch("/grade-catalog/<int:grade_id>")
    @require_roles(RoleName.ADMIN)
    def update_grade(grade_id: int):
        grade = db.session.get(GradeCatalog, grade_id)
        if not grade:
            return api_response(message="Not found", status=404)
        payload = get_json()
        try:
            apply_grade_catalog_payload(grade, payload)
            commit_grade_catalog()
        except ValueError as exc:
            return api_response(message=str(exc), status=400)
        return api_response(grade_to_dict(grade))

    @bp.post("/grades/assign")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def assign_grade():
        payload = get_json()
        employment = db.session.get(Employment, payload.get("employment_id"))
        if not employment:
            return api_response(message="Not found", status=404)

        grade = db.session.get(GradeCatalog, payload.get("grade_id"))
        if not grade:
            return api_response(message="Grade not found", status=404)
        if not grade.is_active:
            return api_response(message="Grade is inactive", status=400)

        assigned_raw = payload.get("assigned_date")
        if not assigned_raw:
            return api_response(message="assigned_date is required", status=400)
        try:
            assigned_date = date.fromisoformat(str(assigned_raw))
        except ValueError:
            return api_response(message="assigned_date must be ISO date", status=400)

        current = (
            EmployeeGradeHistory.query.filter_by(
                employment_id=employment.id,
                valid_to=None,
            ).first()
        )
        if current:
            current.valid_to = assigned_date

        history = EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=grade.id,
            assigned_date=assigned_date,
            assigned_by_id=current_user.id if current_user.is_authenticated else None,
            basis=payload.get("basis"),
        )
        db.session.add(history)
        db.session.flush()
        recalculate_employment_events(employment)
        refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(grade_row_to_dict(employment))

    @bp.get("/passports")
    @login_required
    def list_passports():
        company_id = request.args.get("company_id", 1, type=int)
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            PASSPORT_SORT_FIELDS,
            default_field="valid_until",
            default_direction="asc",
        )

        query = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        ).outerjoin(
            Passport,
            (Passport.person_id == Employment.person_id) & (Passport.is_active.is_(True)),
        )
        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)

        query = apply_sort(query, PASSPORT_SORT_FIELDS, sort, direction)
        return api_response(
            paginate_query(
                query,
                lambda employment: passport_row_to_dict(employment.person, employment),
                page,
                per_page,
            )
        )

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
        db.session.flush()

        employment = (
            Employment.query.filter_by(person_id=person.id)
            .order_by(Employment.hire_date.desc())
            .first()
        )
        if employment:
            recalculate_employment_events(employment)
            refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(passport_row_to_dict(person, employment), status=201)

    @bp.get("/tenure")
    @login_required
    def list_tenure():
        company_id = request.args.get("company_id", 1, type=int)
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            EMPLOYEE_SORT_FIELDS,
            default_field="full_name",
            default_direction="asc",
        )

        active_employments = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        ).all()
        for employment in active_employments:
            ensure_tenure_awards(employment.id, employment.hire_date)
        db.session.commit()

        query = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        )
        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)

        query = apply_sort(query, EMPLOYEE_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, tenure_row_to_dict, page, per_page))

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
