"""Validation, serialization and transactional editing for onboarding."""

from datetime import date
import hashlib
import json

from marshmallow import Schema, fields, validate
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import Conflict, NotFound

from app.extensions import db
from app.models import Company, EmployeeGradeHistory, Employment, Person
from app.models.onboarding import OnboardingCell, OnboardingColumn, OnboardingPlan
from app.services.audit import log_audit
from app.services.onboarding_document_catalog import document_stages


class ColumnSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=256))
    field_type = fields.String(required=True, validate=validate.OneOf(["text", "date", "stage", "checkbox"]))
    responsible_department = fields.String(allow_none=True, validate=validate.Length(max=256))
    document_stage_key = fields.String(allow_none=True, validate=validate.Length(max=64))


class ColumnUpdateSchema(Schema):
    version = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    title = fields.String(validate=validate.Length(min=1, max=256))
    field_type = fields.String(validate=validate.OneOf(["text", "date", "stage", "checkbox"]))
    responsible_department = fields.String(allow_none=True, validate=validate.Length(max=256))
    is_archived = fields.Boolean(truthy={True}, falsy={False})


class CellSchema(Schema):
    version = fields.Integer(required=True, strict=True, validate=validate.Range(min=0))
    column_version = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    clear = fields.Boolean(truthy={True}, falsy={False})
    text_value = fields.String(allow_none=True, validate=validate.Length(max=10000))
    date_value = fields.Date(allow_none=True)
    planned_date = fields.Date(allow_none=True)
    is_completed = fields.Boolean(truthy={True}, falsy={False})
    is_in_progress = fields.Boolean(truthy={True}, falsy={False})
    is_not_required = fields.Boolean(truthy={True}, falsy={False})
    completed_date = fields.Date(allow_none=True)


class PlanSchema(Schema):
    employment_id = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))


class PlanUpdateSchema(Schema):
    version = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    curator_name = fields.String(required=True, allow_none=True, validate=validate.Length(max=256))


class OrderItemSchema(Schema):
    id = fields.Integer(required=True, strict=True)
    version = fields.Integer(required=True, strict=True)


class OrderSchema(Schema):
    columns = fields.List(fields.Nested(OrderItemSchema), required=True)


def lock_company(company_id):
    # Serialize structure/cell edits so archive/type changes cannot race a cell save.
    db.session.execute(select(Company).where(Company.id == company_id).with_for_update()).scalar_one()


def column_dict(column):
    return {key: getattr(column, key) for key in (
        "id", "title", "field_type", "responsible_department", "document_stage_key", "sort_order", "is_archived", "version"
    )}


def cell_dict(cell):
    if cell is None:
        return {"version": 0, "text_value": None, "date_value": None,
                "planned_date": None, "is_completed": False, "is_in_progress": False, "is_not_required": False, "completed_date": None}
    result = {key: getattr(cell, key) for key in (
        "version", "text_value", "date_value", "planned_date", "is_completed", "is_in_progress", "is_not_required", "completed_date"
    )}
    return {key: value.isoformat() if isinstance(value, date) else value for key, value in result.items()}


def onboarding_plan_query(company_id):
    """Return the company-scoped plan query with all display data preloaded."""
    return (
        OnboardingPlan.query.join(Employment)
        .filter(Employment.company_id == company_id)
        .options(
            selectinload(OnboardingPlan.cells),
            selectinload(OnboardingPlan.employment)
            .selectinload(Employment.person)
            .selectinload(Person.name_history),
            selectinload(OnboardingPlan.employment)
            .selectinload(Employment.grade_history)
            .selectinload(EmployeeGradeHistory.grade),
        )
    )


def current_plan_name(plan):
    names = [item for item in plan.employment.person.name_history if item.valid_to is None]
    name = max(names, key=lambda item: (item.valid_from, item.id)) if names else None
    return name.full_name if name else None


def names_match(left, right):
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    folded_left = left.strip().casefold()
    folded_right = right.strip().casefold()
    return bool(folded_left) and folded_left == folded_right


def plan_dict(plan):
    employment = plan.employment
    grades = [item for item in employment.grade_history if item.valid_to is None]
    grade = max(grades, key=lambda item: (item.assigned_date, item.id)) if grades else None
    return {
        "id": plan.id,
        "employment_id": employment.id,
        "full_name": current_plan_name(plan),
        "grade": grade.grade.name if grade else None,
        "employment_status": employment.status,
        "hire_date": employment.hire_date.isoformat(),
        "curator_name": plan.curator_name,
        "version": plan.version,
        "cells": {str(cell.column_id): cell_dict(cell) for cell in plan.cells},
    }


def find_column(column_id, company_id):
    column = OnboardingColumn.query.filter_by(id=column_id, company_id=company_id).first()
    if column is None:
        raise NotFound()
    return column


def find_plan(plan_id, company_id):
    from app.models import Employment
    plan = OnboardingPlan.query.join(Employment).filter(
        OnboardingPlan.id == plan_id, Employment.company_id == company_id
    ).first()
    if plan is None:
        raise NotFound()
    return plan


def check_version(expected, actual):
    if expected != actual:
        raise Conflict("Данные изменены другим пользователем. Обновите таблицу перед повторным сохранением.")


def validate_document_mapping(company_id, payload, exclude_id=None):
    key = payload.get("document_stage_key")
    if not key:
        payload["document_stage_key"] = None
        return
    if key not in document_stages():
        raise ValueError("Неизвестный этап документа")
    if payload.get("field_type") not in (None, "stage"):
        raise ValueError("Сопоставление доступно только для этапов с датами")
    query = OnboardingColumn.query.filter_by(company_id=company_id, document_stage_key=key)
    if exclude_id is not None:
        query = query.filter(OnboardingColumn.id != exclude_id)
    if query.first():
        raise ValueError("Этот этап документа уже сопоставлен")

def save_column(column, payload):
    check_version(payload.pop("version"), column.version)
    old = column_dict(column)
    if "title" in payload:
        payload["title"] = payload["title"].strip()
        if not payload["title"]:
            raise ValueError("Название столбца не может быть пустым")
    if payload.get("field_type", column.field_type) != column.field_type:
        filled = OnboardingCell.query.filter(
            OnboardingCell.column_id == column.id,
            db.or_(OnboardingCell.text_value.isnot(None), OnboardingCell.date_value.isnot(None),
                   OnboardingCell.planned_date.isnot(None), OnboardingCell.is_completed.is_(True),
                   OnboardingCell.is_not_required.is_(True), OnboardingCell.is_in_progress.is_(True)),
        ).first()
        if filled:
            raise ValueError("Нельзя изменить тип заполненного столбца")
    if "responsible_department" in payload:
        payload["responsible_department"] = (payload["responsible_department"] or "").strip() or None
    if "document_stage_key" in payload:
        validate_document_mapping(column.company_id, payload, column.id)
    for key, value in payload.items():
        setattr(column, key, value)
    db.session.flush()
    log_audit("update", "onboarding_column", column.id, old, column_dict(column))


def save_cell(plan, column, payload):
    check_version(payload.pop("column_version"), column.version)
    if column.is_archived:
        raise Conflict("Столбец архивирован. Обновите таблицу.")
    allowed = {"text": {"text_value"}, "date": {"date_value"},
               "stage": {"planned_date", "is_completed", "completed_date", "is_not_required", "is_in_progress"},
               "checkbox": {"is_completed", "is_not_required", "is_in_progress"}}[column.field_type]
    version = payload.pop("version")
    clear = payload.pop("clear", False)
    if clear and payload:
        raise ValueError("Очистку нельзя совмещать с изменением значения")
    if set(payload) - allowed:
        raise ValueError("Значение не соответствует типу столбца")
    cell = OnboardingCell.query.filter_by(plan_id=plan.id, column_id=column.id).first()
    check_version(version, cell.version if cell else 0)
    old = cell_dict(cell)
    if clear:
        # Keep a versioned empty cell: deleting it would allow an old version=0
        # editor to overwrite the cleared value (an ABA concurrency bug).
        if cell is None:
            cell = OnboardingCell(plan_id=plan.id, column_id=column.id)
            db.session.add(cell)
        else:
            cell.version += 1
        cell.text_value = cell.date_value = cell.planned_date = cell.completed_date = None
        cell.is_completed = cell.is_not_required = cell.is_in_progress = False
        db.session.flush()
        log_audit("clear", "onboarding_cell", cell.id,
                  {"plan_id": plan.id, "column_id": column.id, **old},
                  {"plan_id": plan.id, "column_id": column.id, **cell_dict(cell)})
        return cell
    values = {key: getattr(cell, key) if cell else None for key in allowed}
    for flag in ("is_completed", "is_not_required", "is_in_progress"):
        if flag in values and values[flag] is None:
            values[flag] = False
    values.update(payload)
    if column.field_type in ("stage", "checkbox"):
        flags = ("is_completed", "is_not_required", "is_in_progress")
        selected = [flag for flag in flags if payload.get(flag)]
        if len(selected) > 1:
            raise ValueError("У этапа может быть только одно состояние")
        if selected:
            for flag in flags:
                values[flag] = flag == selected[0]
        if sum(bool(values[flag]) for flag in flags) > 1:
            raise ValueError("У этапа может быть только одно состояние")
    if column.field_type == "stage":
        if values["is_completed"] and not values["completed_date"]:
            raise ValueError("Укажите дату выполнения")
        if not values["is_completed"]:
            values["completed_date"] = None
    if column.field_type == "text" and values["text_value"] == "":
        values["text_value"] = None
    if cell is None:
        cell = OnboardingCell(plan_id=plan.id, column_id=column.id)
        db.session.add(cell)
    for key, value in values.items():
        setattr(cell, key, value)
    if column.field_type == "checkbox":
        cell.planned_date = None
        cell.completed_date = None
    db.session.flush()
    log_audit("update", "onboarding_cell", cell.id,
              {"plan_id": plan.id, "column_id": column.id, **old},
              {"plan_id": plan.id, "column_id": column.id, **cell_dict(cell)})
    return cell


def save_plan(plan, payload):
    check_version(payload["version"], plan.version)
    old = {"curator_name": plan.curator_name, "version": plan.version}
    name = payload["curator_name"]
    plan.curator_name = (name.strip() or None) if name is not None else None
    db.session.flush()
    log_audit("update", "onboarding_plan", plan.id, old,
              {"curator_name": plan.curator_name, "version": plan.version})


class DeleteSchema(Schema):
    version = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    snapshot = fields.String(required=True, validate=validate.Regexp(r"^[0-9a-f]{64}$"))


class EmployeeDeleteSchema(DeleteSchema):
    delete_onboarding_plan = fields.Boolean(required=True, truthy={True}, falsy={False}, validate=validate.Equal(True))


def newest_plans(query):
    return query.order_by(OnboardingPlan.created_at.desc(), OnboardingPlan.id.desc())


def _snapshot(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def plan_delete_preview(plan):
    value = plan_dict(plan)
    return {"version": plan.version, "snapshot": _snapshot(value),
            "cell_count": len(plan.cells), "full_name": value["full_name"],
            "hire_date": value["hire_date"]}


def column_delete_preview(column):
    cells = OnboardingCell.query.filter_by(column_id=column.id).order_by(OnboardingCell.id).all()
    value = {"column": column_dict(column), "cells": [
        {"id": c.id, "plan_id": c.plan_id, **cell_dict(c)} for c in cells]}
    return {"version": column.version, "snapshot": _snapshot(value), "cell_count": len(cells), "title": column.title}


def check_delete_preview(payload, preview):
    check_version(payload["version"], preview["version"])
    if payload["snapshot"] != preview["snapshot"]:
        raise Conflict("Данные изменились после подтверждения. Проверьте их и подтвердите удаление заново.")


def delete_plan(plan, payload):
    check_delete_preview(payload, plan_delete_preview(plan))
    old = plan_dict(plan)
    log_audit("delete", "onboarding_plan", plan.id, old, None)
    for cell in list(plan.cells):
        db.session.delete(cell)
    db.session.flush()
    db.session.delete(plan)
    db.session.flush()


def delete_column(column, payload):
    check_delete_preview(payload, column_delete_preview(column))
    cells = OnboardingCell.query.filter_by(column_id=column.id).all()
    old = {"column": column_dict(column), "cells": [
        {"id": c.id, "plan_id": c.plan_id, **cell_dict(c)} for c in cells]}
    log_audit("delete", "onboarding_column", column.id, old, None)
    for cell in cells:
        db.session.delete(cell)
    db.session.flush()
    db.session.delete(column)
    db.session.flush()
