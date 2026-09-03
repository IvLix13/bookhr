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
    join_current_grade_history,
    join_current_person_name,
    load_schema,
    nearest_eligible_date_sort_key,
    paginate_query,
    paginate_sequence,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
    sort_sequence_with_nulls_last,
)
from app.api.schemas import CreateContractSchema, UpdateContractSchema, UpdateTenureAwardSchema
from app.api.serializers import (
    contract_to_dict,
    grade_row_to_dict,
    grade_to_dict,
    passport_row_to_dict,
    tenure_award_to_dict,
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
    delete_grade_catalog,
    validate_extra_year_without_university,
    validate_min_years,
    validate_rank,
)
from app.services.grades import assign_grade_to_employment, compute_grade_eligibility
from app.services.rule_engine import apply_contract_report_date, recalculate_employment_events
from app.services.tenure import (
    active_employment,
    ensure_tenure_awards,
    tenure_years,
    total_tenure_years,
)
from app.tenant import get_request_company_id
from app.utils.dates import calculate_contract_start


CONTRACT_SORT_FIELDS = {
    "end_date": Contract.end_date,
    "start_date": Contract.start_date,
    "term_years": Contract.term_years,
    "days_left": Contract.end_date,
    "full_name": PersonNameHistory.full_name,
}

CONTRACT_SORT_ALIASES = {
    "days_left": "end_date",
}

EMPLOYEE_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "hire_date": Employment.hire_date,
}

TENURE_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "hire_date": Employment.hire_date,
    "tenure_years": Employment.hire_date,
    "continuous_tenure_years": Employment.hire_date,
}

PASSPORT_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "valid_until": Passport.valid_until,
    "days_left": Passport.valid_until,
    "status": Passport.valid_until,
}

PASSPORT_SORT_ALIASES = {
    "days_left": "valid_until",
    "status": "valid_until",
}

GRADE_ELIGIBLE_NEAREST_SORT = "eligible_date_nearest"

GRADE_SORT_FIELDS = {
    "full_name": PersonNameHistory.full_name,
    "hire_date": Employment.hire_date,
    "grade": GradeCatalog.name,
    "grade_date": EmployeeGradeHistory.assigned_date,
    GRADE_ELIGIBLE_NEAREST_SORT: Employment.hire_date,
    "eligible_date": Employment.hire_date,
    "days_left": Employment.hire_date,
}

GRADE_COMPUTED_SORTS = frozenset({"days_left", "eligible_date", GRADE_ELIGIBLE_NEAREST_SORT})


def _sort_employments_by_grade_computed(
    employments: list[Employment],
    sort: str,
    direction: str,
) -> None:
    if sort == GRADE_ELIGIBLE_NEAREST_SORT:
        def nearest_key(employment: Employment) -> tuple:
            eligibility = compute_grade_eligibility(employment)
            return nearest_eligible_date_sort_key(
                eligibility.get("eligible_date"),
                is_available=bool(eligibility.get("is_available")),
                tie_breaker=employment.id,
            )

        employments.sort(key=nearest_key)
        return

    reverse = direction == "desc"

    def sort_value(employment: Employment) -> int | None:
        eligibility = compute_grade_eligibility(employment)
        value = eligibility.get(sort)
        if sort == "eligible_date":
            return value.toordinal() if value is not None else None
        return value

    sort_sequence_with_nulls_last(employments, sort_value, reverse=reverse)


def register_routes(bp):
    @bp.get("/contracts")
    @login_required
    def list_contracts():
        company_id = get_request_company_id()
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            CONTRACT_SORT_FIELDS,
            default_field="end_date",
            default_direction="asc",
            aliases=CONTRACT_SORT_ALIASES,
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
        payload = load_schema(CreateContractSchema)
        end_date = payload["end_date"]
        term_years = payload["term_years"]
        start_date = calculate_contract_start(end_date, term_years)
        contract = Contract(
            employment_id=payload["employment_id"],
            start_date=start_date,
            end_date=end_date,
            term_years=term_years,
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

    @bp.patch("/contracts/<int:contract_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_contract(contract_id: int):
        contract = db.session.get(Contract, contract_id)
        if not contract or contract.employment.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)

        payload = load_schema(UpdateContractSchema)
        if "end_date" in payload or "term_years" in payload:
            end_date = payload.get("end_date", contract.end_date)
            term_years = payload.get("term_years", contract.term_years)
            if end_date is None or term_years is None:
                return api_response(
                    message="Укажите срок договора и дату окончания",
                    status=400,
                )
            contract.end_date = end_date
            contract.term_years = term_years
            contract.start_date = calculate_contract_start(end_date, term_years)

        if "notes" in payload:
            contract.notes = payload.get("notes")

        if contract.end_date <= contract.start_date:
            return api_response(message="Дата окончания договора должна быть позже даты начала", status=400)

        db.session.flush()
        recalculate_employment_events(contract.employment)
        if payload.get("report_date") is not None:
            apply_contract_report_date(contract, payload["report_date"])
        refresh_overdue_events(contract.employment.company_id)
        db.session.commit()
        return api_response(contract_to_dict(contract))

    @bp.get("/grades")
    @login_required
    def list_grades():
        company_id = get_request_company_id()
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            GRADE_SORT_FIELDS,
            default_field=GRADE_ELIGIBLE_NEAREST_SORT,
            default_direction="asc",
        )

        query = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        )
        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)

        if sort in GRADE_COMPUTED_SORTS:
            employments = query.all()
            _sort_employments_by_grade_computed(employments, sort, direction)
            rows = [grade_row_to_dict(employment) for employment in employments]
            return api_response(paginate_sequence(rows, page, per_page))

        if sort == "grade_date" or sort == "grade":
            query = join_current_grade_history(query)
            if sort == "grade":
                query = query.outerjoin(
                    GradeCatalog,
                    GradeCatalog.id == EmployeeGradeHistory.grade_id,
                )

        query = apply_sort(query, GRADE_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, grade_row_to_dict, page, per_page))

    @bp.get("/grade-catalog")
    @login_required
    def list_grade_catalog():
        grades = GradeCatalog.query.order_by(
            GradeCatalog.rank.asc(),
            GradeCatalog.name.asc(),
            GradeCatalog.id.asc(),
        ).all()
        return api_response([grade_to_dict(g, include_usage=True) for g in grades])

    @bp.post("/grade-catalog")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_grade():
        payload = get_json()
        try:
            name = str(payload.get("name", "")).strip()
            if not name:
                raise ValueError("name is required")
            rank = validate_rank(payload["rank"])
            min_years = validate_min_years(payload.get("min_years", 1))
            grade = GradeCatalog(
                name=name,
                rank=rank,
                min_years=min_years,
                extra_year_without_university=validate_extra_year_without_university(
                    payload.get("extra_year_without_university", False)
                ),
            )
            db.session.add(grade)
            commit_grade_catalog()
        except ValueError as exc:
            return api_response(message=str(exc), status=400)
        return api_response(grade_to_dict(grade), status=201)

    @bp.patch("/grade-catalog/<int:grade_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
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
        return api_response(grade_to_dict(grade, include_usage=True))

    @bp.delete("/grade-catalog/<int:grade_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def delete_grade(grade_id: int):
        grade = db.session.get(GradeCatalog, grade_id)
        if not grade:
            return api_response(message="Not found", status=404)
        try:
            delete_grade_catalog(grade)
        except ValueError as exc:
            return api_response(message=str(exc), status=400)
        return api_response({"id": grade_id})

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

        try:
            assign_grade_to_employment(
                employment,
                grade,
                assigned_date,
                basis=payload.get("basis"),
                assigned_by_id=current_user.id if current_user.is_authenticated else None,
            )
        except ValueError as exc:
            return api_response(message=str(exc), status=400)
        recalculate_employment_events(employment)
        refresh_overdue_events(employment.company_id)
        db.session.commit()
        return api_response(grade_row_to_dict(employment))

    @bp.get("/passports")
    @login_required
    def list_passports():
        company_id = get_request_company_id()
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            PASSPORT_SORT_FIELDS,
            default_field="valid_until",
            default_direction="asc",
            aliases=PASSPORT_SORT_ALIASES,
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
        company_id = get_request_company_id()
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            TENURE_SORT_FIELDS,
            default_field="tenure_years",
            default_direction="desc",
        )

        active_employments = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        ).all()
        for employment in active_employments:
            ensure_tenure_awards(employment.person_id, employment.company_id)
            recalculate_employment_events(employment)
        db.session.commit()

        query = Employment.query.filter_by(
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        )
        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)

        if sort == "tenure_years":
            employments = query.all()
            sort_sequence_with_nulls_last(
                employments,
                lambda row: total_tenure_years(row.person_id, row.company_id),
                reverse=direction == "desc",
            )
            rows = [tenure_row_to_dict(employment) for employment in employments]
            return api_response(paginate_sequence(rows, page, per_page))

        if sort == "continuous_tenure_years":
            employments = query.all()
            sort_sequence_with_nulls_last(
                employments,
                lambda row: tenure_years(row.hire_date),
                reverse=direction == "desc",
            )
            rows = [tenure_row_to_dict(employment) for employment in employments]
            return api_response(paginate_sequence(rows, page, per_page))

        query = apply_sort(query, TENURE_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, tenure_row_to_dict, page, per_page))

    @bp.patch("/tenure/<int:award_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_tenure_award(award_id: int):
        from app.models import TenureAward

        award = db.session.get(TenureAward, award_id)
        if not award or award.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)

        raw = get_json()
        load_schema(UpdateTenureAwardSchema)

        ensure_tenure_awards(award.person_id, award.company_id)
        db.session.refresh(award)

        if "is_received" in raw:
            award.is_received = bool(raw["is_received"])
            if not award.is_received:
                award.received_date = None

        if "received_date" in raw:
            value = raw["received_date"]
            if value in (None, ""):
                award.received_date = None
            else:
                award.received_date = date.fromisoformat(str(value))
        elif raw.get("is_received") and award.received_date is None:
            award.received_date = award.milestone_date

        employment = active_employment(award.person_id, award.company_id)
        if employment:
            recalculate_employment_events(employment)

        db.session.commit()
        return api_response(tenure_award_to_dict(award))
