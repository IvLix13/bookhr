"""Company-scoped onboarding API."""

from functools import wraps
from math import ceil

from flask import send_file
from flask_login import login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.exceptions import Conflict, NotFound

from app.api.helpers import api_response, apply_employment_name_search, get_json, parse_pagination_args, parse_search_q, require_roles
from app.extensions import db
from app.models import Employment, RoleName
from app.models.onboarding import OnboardingColumn, OnboardingPlan
from app.services.audit import log_audit
from app.services.onboarding import (
    CellSchema, ColumnSchema, ColumnUpdateSchema, OrderSchema, PlanSchema,
    cell_dict, check_version, column_dict, find_column, find_plan,
    lock_company, onboarding_plan_query, plan_dict, save_cell, save_column,
)
from app.services.onboarding_export import build_onboarding_workbook
from app.tenant import get_request_company_id


def transaction(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            lock_company(get_request_company_id())
            result = fn(*args, **kwargs)
            db.session.commit()
            return result
        except (IntegrityError, StaleDataError):
            db.session.rollback()
            raise Conflict("Данные уже изменены или план существует. Обновите таблицу.")
        except Exception:
            db.session.rollback()
            raise
    return wrapped


def register_routes(bp):
    @bp.get("/onboarding/columns")
    @login_required
    def onboarding_columns():
        columns = OnboardingColumn.query.filter_by(company_id=get_request_company_id()).order_by(
            OnboardingColumn.sort_order, OnboardingColumn.id).all()
        return api_response([column_dict(c) for c in columns])

    @bp.post("/onboarding/columns")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_create_column():
        payload = ColumnSchema().load(get_json())
        payload["title"] = payload["title"].strip()
        if not payload["title"]:
            raise ValueError("Название столбца не может быть пустым")
        company_id = get_request_company_id()
        last = db.session.query(db.func.max(OnboardingColumn.sort_order)).filter_by(company_id=company_id).scalar()
        column = OnboardingColumn(company_id=company_id, sort_order=(last or 0) + 1, **payload)
        db.session.add(column)
        db.session.flush()
        log_audit("create", "onboarding_column", column.id, None, column_dict(column))
        return api_response(column_dict(column), status=201)

    @bp.patch("/onboarding/columns/<int:column_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_update_column(column_id):
        column = find_column(column_id, get_request_company_id())
        save_column(column, ColumnUpdateSchema().load(get_json()))
        return api_response(column_dict(column))

    @bp.patch("/onboarding/columns/order")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_order():
        payload = OrderSchema().load(get_json())["columns"]
        columns = OnboardingColumn.query.filter_by(company_id=get_request_company_id()).all()
        by_id = {c.id: c for c in columns}
        ids = [item["id"] for item in payload]
        if len(ids) != len(set(ids)) or set(ids) != set(by_id):
            raise Conflict("Структура изменилась. Обновите список столбцов.")
        for item in payload:
            check_version(item["version"], by_id[item["id"]].version)
        old = [column_dict(c) for c in columns]
        for order, item in enumerate(payload):
            by_id[item["id"]].sort_order = order
        db.session.flush()
        result = [column_dict(by_id[id_]) for id_ in ids]
        log_audit("reorder", "onboarding_columns", None, {"columns": old}, {"columns": result})
        return api_response(result)

    @bp.get("/onboarding/plans")
    @login_required
    def onboarding_plans():
        page, per_page = parse_pagination_args()
        query = onboarding_plan_query(get_request_company_id())
        query = apply_employment_name_search(query, parse_search_q())
        total = query.count()
        plans = query.order_by(OnboardingPlan.id).offset((page - 1) * per_page).limit(per_page).all()
        return api_response({"items": [plan_dict(p) for p in plans], "page": page,
                             "per_page": per_page, "total": total, "pages": ceil(total / per_page)})

    @bp.get("/onboarding/export")
    @login_required
    def onboarding_export():
        return send_file(
            build_onboarding_workbook(get_request_company_id()),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="onboarding_plan.xlsx",
        )

    @bp.get("/onboarding/plans/<int:plan_id>")
    @login_required
    def onboarding_plan(plan_id):
        return api_response(plan_dict(find_plan(plan_id, get_request_company_id())))

    @bp.post("/onboarding/plans")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_create_plan():
        payload = PlanSchema().load(get_json())
        employment = Employment.query.filter_by(id=payload["employment_id"], company_id=get_request_company_id()).first()
        if employment is None:
            raise NotFound()
        if OnboardingPlan.query.filter_by(employment_id=employment.id).first():
            raise Conflict("План для этого периода трудоустройства уже существует")
        plan = OnboardingPlan(employment_id=employment.id)
        db.session.add(plan)
        db.session.flush()
        log_audit("create", "onboarding_plan", plan.id, None, {"employment_id": employment.id})
        return api_response(plan_dict(plan), status=201)

    @bp.patch("/onboarding/plans/<int:plan_id>/cells/<int:column_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR, RoleName.VIEWER)
    @transaction
    def onboarding_update_cell(plan_id, column_id):
        company_id = get_request_company_id()
        cell = save_cell(find_plan(plan_id, company_id), find_column(column_id, company_id), CellSchema().load(get_json()))
        return api_response(cell_dict(cell))
