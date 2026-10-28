"""Validate a complete wizard without creating persistent draft records."""
from types import SimpleNamespace
from marshmallow import Schema, fields, validate
from werkzeug.exceptions import Conflict, NotFound
from app.models import Employment
from app.models.onboarding import OnboardingColumn, OnboardingPlan
from app.services.employees import get_current_name
from app.services.onboarding import CellSchema, check_version


class WizardCellSchema(Schema):
    column_id = fields.Integer(required=True, strict=True)
    column_version = fields.Integer(required=True, strict=True)
    values = fields.Dict(required=True)


class WizardSchema(Schema):
    employment_id = fields.Integer(required=True, strict=True)
    mentor_id = fields.Integer(required=True, strict=True)
    cells = fields.List(fields.Nested(WizardCellSchema), required=True, validate=validate.Length(max=1000))


def validate_wizard(payload, company_id):
    body = WizardSchema().load(payload)
    employee = Employment.query.filter_by(id=body['employment_id'], company_id=company_id).first()
    mentor = Employment.query.filter_by(id=body['mentor_id'], company_id=company_id, status='active').first()
    if employee is None or mentor is None:
        raise NotFound('Сотрудник или действующий наставник не найден')
    if employee.person_id == mentor.person_id:
        raise ValueError('Сотрудник не может быть собственным наставником')
    if OnboardingPlan.query.filter_by(employment_id=employee.id).first():
        raise Conflict('План для этого периода трудоустройства уже существует')
    columns = OnboardingColumn.query.filter_by(company_id=company_id, is_archived=False).all()
    supplied = body['cells']
    if len(supplied) != len(columns) or {c['column_id'] for c in supplied} != {c.id for c in columns}:
        raise Conflict('Состав мероприятий изменился. Обновите структуру плана.')
    by_id = {c.id: c for c in columns}
    cells, normalized = [], []
    for item in supplied:
        column = by_id[item['column_id']]
        check_version(item['column_version'], column.version)
        raw = {key: None if value == '' and key.endswith(('date', 'value')) else value for key, value in item['values'].items()}
        values = CellSchema().load(dict(raw, version=0, column_version=column.version))
        allowed = {'text': {'text_value'}, 'date': {'date_value'},
                   'stage': {'planned_date', 'completed_date', 'is_completed'},
                   'checkbox': {'is_completed'}}[column.field_type]
        if set(item['values']) - allowed:
            raise ValueError('Значение не соответствует типу поля')
        if column.field_type == 'stage':
            if not values.get('planned_date'):
                raise ValueError('Укажите все плановые даты')
            if values.get('is_completed') and not values.get('completed_date'):
                raise ValueError('Укажите фактическую дату выполнения')
            if not values.get('is_completed') and values.get('completed_date'):
                raise ValueError('Фактическая дата допустима только для выполненного этапа')
        normalized.append((column, values))
        cells.append(SimpleNamespace(column_id=column.id, planned_date=values.get('planned_date'), is_not_required=False))
    name = get_current_name(mentor.person)
    if not name:
        raise ValueError('У наставника не заполнено ФИО')
    draft = SimpleNamespace(employment=employee, curator_name=name, cells=cells)
    return draft, normalized
