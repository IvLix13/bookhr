"""Company-scoped onboarding API."""

from functools import wraps
from math import ceil

from flask import send_file, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.exceptions import Conflict, Forbidden, NotFound

from app.api.helpers import api_response, apply_employment_name_search, get_json, parse_pagination_args, parse_search_q, require_roles
from app.extensions import db
from app.models import Company, Employment, RoleName
from app.models.onboarding import OnboardingColumn, OnboardingPlan
from app.services.audit import log_audit
from app.services.onboarding import (
    DeleteSchema, delete_plan, delete_column, plan_delete_preview, column_delete_preview, newest_plans,
    CellSchema, ColumnSchema, ColumnUpdateSchema, OrderSchema, PlanSchema, PlanUpdateSchema,
    cell_dict, check_version, column_dict, current_plan_name, find_column, find_plan,
    lock_company, names_match, onboarding_plan_query, plan_dict, save_cell, save_column, save_plan, validate_document_mapping,
)
from app.services.onboarding_export import build_onboarding_workbook
from app.services.onboarding_docx import build_onboarding_document
from app.services.onboarding_document_catalog import document_stages
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
    @bp.get("/onboarding/document-stages")
    @login_required
    def onboarding_document_stages():
        from app.services.onboarding_document_catalog import document_variables
        variables = document_variables()
        return api_response([{"key": key, "title": title,
            "date_placeholder": next(("{{ " + name + " }}" for name, source in variables.items() if source == f"stages.{key}.planned_date"), None),
            "department_placeholder": next(("{{ " + name + " }}" for name, source in variables.items() if source == f"stages.{key}.department"), None)}
            for key, title in document_stages().items()])

    @bp.get("/onboarding/docx-template/info")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def onboarding_template_info():
        company = Company.query.filter_by(id=get_request_company_id()).first_or_404()
        return api_response({"version": company.onboarding_template_version})

    @bp.get("/onboarding/docx-template")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def onboarding_template_download():
        from app.services.onboarding_docx import template_source
        return send_file(template_source(get_request_company_id()), as_attachment=True,
            download_name="onboarding_template.docx", mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    @bp.post("/onboarding/docx-template")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_template_upload():
        from app.services.onboarding_docx import validate_template
        company_id = get_request_company_id()
        company = Company.query.filter_by(id=company_id).first_or_404()
        uploaded = request.files.get("file")
        if uploaded is None or not (uploaded.filename or "").lower().endswith(".docx"):
            raise ValueError("Выберите файл DOCX")
        try:
            version = int(request.form.get("version", ""))
        except ValueError:
            raise ValueError("Не указана версия шаблона")
        data = uploaded.stream.read(5 * 1024 * 1024 + 1)
        validate_template(data)
        updated = Company.query.filter_by(id=company_id, onboarding_template_version=version).update(
            {"onboarding_docx_template": data, "onboarding_template_version": version + 1}, synchronize_session=False)
        if not updated:
            raise Conflict("Шаблон уже изменён. Повторите загрузку после обновления.")
        log_audit("update", "onboarding_template", company_id, {"version": version}, {"version": version + 1})
        return api_response({"version": version + 1})

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
        validate_document_mapping(company_id, payload)
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
        plans = newest_plans(query).offset((page - 1) * per_page).limit(per_page).all()
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

    @bp.get("/onboarding/plans/<int:plan_id>/docx")
    @login_required
    def onboarding_plan_docx(plan_id):
        plan = find_plan(plan_id, get_request_company_id())
        return send_file(build_onboarding_document(plan),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True, download_name="onboarding_plan.docx")

    @bp.get("/onboarding/plans/<int:plan_id>")
    @login_required
    def onboarding_plan(plan_id):
        return api_response(plan_dict(find_plan(plan_id, get_request_company_id())))

    @bp.post("/onboarding/plans/draft-docx")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_draft_docx():
        from app.services.onboarding_wizard import validate_wizard
        draft, _ = validate_wizard(get_json(), get_request_company_id())
        return send_file(build_onboarding_document(draft),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True, download_name="onboarding_plan.docx")

    @bp.post("/onboarding/plans/from-wizard")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_from_wizard():
        from app.services.onboarding_wizard import validate_wizard
        draft, cells = validate_wizard(get_json(), get_request_company_id())
        plan = OnboardingPlan(employment_id=draft.employment.id, curator_name=draft.curator_name)
        db.session.add(plan)
        db.session.flush()
        for column, values in cells:
            save_cell(plan, column, dict(values))
        log_audit("create", "onboarding_plan", plan.id, None,
                  {"employment_id": plan.employment_id, "curator_name": plan.curator_name})
        db.session.expire(plan, ['cells'])
        return api_response(plan_dict(plan), status=201)

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

    @bp.patch("/onboarding/plans/<int:plan_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_update_plan(plan_id):
        plan = find_plan(plan_id, get_request_company_id())
        save_plan(plan, PlanUpdateSchema().load(get_json()))
        return api_response(plan_dict(plan))

    @bp.patch("/onboarding/plans/<int:plan_id>/cells/<int:column_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR, RoleName.VIEWER)
    @transaction
    def onboarding_update_cell(plan_id, column_id):
        company_id = get_request_company_id()
        plan = find_plan(plan_id, company_id)
        if current_user.has_role(RoleName.VIEWER) and not names_match(current_user.full_name, current_plan_name(plan)):
            raise Forbidden("Можно изменять только этапы сотрудника с совпадающим ФИО")
        cell = save_cell(plan, find_column(column_id, company_id), CellSchema().load(get_json()))
        return api_response(cell_dict(cell))


    @bp.get("/onboarding/plans/<int:plan_id>/delete-preview")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def onboarding_plan_delete_preview(plan_id):
        return api_response(plan_delete_preview(find_plan(plan_id, get_request_company_id())))

    @bp.delete("/onboarding/plans/<int:plan_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_delete_plan(plan_id):
        delete_plan(find_plan(plan_id, get_request_company_id()), DeleteSchema().load(get_json()))
        return api_response(message="План удалён")

    @bp.get("/onboarding/columns/<int:column_id>/delete-preview")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def onboarding_column_delete_preview(column_id):
        return api_response(column_delete_preview(find_column(column_id, get_request_company_id())))

    @bp.delete("/onboarding/columns/<int:column_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    @transaction
    def onboarding_delete_column(column_id):
        delete_column(find_column(column_id, get_request_company_id()), DeleteSchema().load(get_json()))
        return api_response(message="Поле удалено")
