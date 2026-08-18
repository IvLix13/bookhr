"""Marshmallow schemas for API input validation."""

from __future__ import annotations

from datetime import date

from marshmallow import Schema, ValidationError, fields, validate, validates_schema, EXCLUDE

from app.models import EducationStatus, EventType, RoleName


EDUCATION_CHOICES = (EducationStatus.YES.value, EducationStatus.NO.value)


class BaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class DateField(fields.Date):
    """ISO date field with clear validation errors."""

    def _deserialize(self, value, attr, data, **kwargs):
        if value is None or value == "":
            return None
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ValidationError("Invalid date format, expected YYYY-MM-DD") from exc


class EventTypeField(fields.Field):
    def _deserialize(self, value, attr, data, **kwargs):
        if value is None or value == "":
            return EventType.MANUAL
        try:
            return EventType(str(value))
        except ValueError as exc:
            raise ValidationError(f"Invalid event type: {value}") from exc


class CreateEventSchema(BaseSchema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=512))
    event_date = DateField(required=True)
    event_type = EventTypeField(load_default=EventType.MANUAL)
    description = fields.Str(allow_none=True)
    employment_id = fields.Int(allow_none=True)


class UpdateEventSchema(BaseSchema):
    title = fields.Str(validate=validate.Length(min=1, max=512))
    event_date = DateField()
    event_type = EventTypeField()
    description = fields.Str(allow_none=True)
    employment_id = fields.Int(allow_none=True)


class EventActionSchema(BaseSchema):
    comment = fields.Str(allow_none=True)
    extension_term_years = fields.Float(allow_none=True)
    new_end_date = DateField(allow_none=True)
    target_grade_id = fields.Int(allow_none=True)
    new_passport_valid_until = DateField(allow_none=True)


class CreateEmployeeSchema(BaseSchema):
    full_name = fields.Str(required=True, validate=validate.Length(min=1, max=256))
    hire_date = DateField(required=True)
    title = fields.Str(load_default="Не указана")
    position_grade_id = fields.Int(allow_none=True)
    actual_grade_id = fields.Int(allow_none=True)
    grade_date = DateField(allow_none=True)
    contract_end = DateField(allow_none=True)
    contract_term_years = fields.Float(allow_none=True)
    passport_until = DateField(allow_none=True)
    education_status = fields.Str(required=True, validate=validate.OneOf(EDUCATION_CHOICES))

    @validates_schema
    def validate_dates(self, data, **kwargs):
        hire_date = data.get("hire_date")
        contract_end = data.get("contract_end")
        if hire_date and contract_end and contract_end <= hire_date:
            raise ValidationError({"contract_end": ["Дата окончания договора должна быть позже даты начала работы"]})


class UpdateEmployeeSchema(BaseSchema):
    full_name = fields.Str(validate=validate.Length(min=1, max=256))
    hire_date = DateField(allow_none=True)
    title = fields.Str(allow_none=True)
    position_grade_id = fields.Int(allow_none=True)
    actual_grade_id = fields.Int(allow_none=True)
    grade_date = DateField(allow_none=True)
    contract_end = DateField(allow_none=True)
    contract_term_years = fields.Float(allow_none=True)
    passport_until = DateField(allow_none=True)
    education_status = fields.Str(validate=validate.OneOf(EDUCATION_CHOICES))
    effective_date = DateField(allow_none=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        hire_date = data.get("hire_date")
        contract_end = data.get("contract_end")
        if hire_date and contract_end and contract_end <= hire_date:
            raise ValidationError({"contract_end": ["Дата окончания договора должна быть позже даты начала работы"]})


class DismissEmployeeSchema(BaseSchema):
    dismissal_date = DateField(allow_none=True)
    reason = fields.Str(allow_none=True)


class RehireEmployeeSchema(BaseSchema):
    hire_date = DateField(required=True)
    title = fields.Str(load_default="Не указана")
    position_grade_id = fields.Int(allow_none=True)
    actual_grade_id = fields.Int(allow_none=True)
    grade_date = DateField(allow_none=True)
    contract_end = DateField(allow_none=True)
    contract_term_years = fields.Float(allow_none=True)
    passport_until = DateField(allow_none=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        hire_date = data.get("hire_date")
        contract_end = data.get("contract_end")
        if hire_date and contract_end and contract_end <= hire_date:
            raise ValidationError({"contract_end": ["Дата окончания договора должна быть позже даты начала работы"]})


class CreateUserSchema(BaseSchema):
    username = fields.Str(required=True, validate=validate.Length(min=1, max=64))
    password = fields.Str(required=True, validate=validate.Length(min=1))
    full_name = fields.Str(required=True, validate=validate.Length(min=1, max=256))
    role = fields.Str(required=True)


class UpdateUserSchema(BaseSchema):
    full_name = fields.Str(validate=validate.Length(min=1, max=256))
    role = fields.Str()
    is_active = fields.Bool()


class ResetPasswordSchema(BaseSchema):
    password = fields.Str(required=True, validate=validate.Length(min=1))


class CreateRewardSchema(BaseSchema):
    employment_id = fields.Int(required=True)
    reward_type = fields.Str(required=True)
    directive_text = fields.Str(allow_none=True)
    delivered_date = DateField(allow_none=True)
    status = fields.Str(allow_none=True)
    notes = fields.Str(allow_none=True)


class AssignGradeSchema(BaseSchema):
    employment_id = fields.Int(required=True)
    grade_id = fields.Int(required=True)
    assigned_date = DateField(required=True)
    basis = fields.Str(allow_none=True)


class CreateGradeCatalogSchema(BaseSchema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=128))
    rank = fields.Int(required=True)
    min_years = fields.Float(load_default=0)
    extra_year_without_university = fields.Bool(load_default=False)


class CreateContractSchema(BaseSchema):
    employment_id = fields.Int(required=True)
    start_date = DateField(required=True)
    end_date = DateField(allow_none=True)
    term_years = fields.Float(allow_none=True)
    notes = fields.Str(allow_none=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date and end_date and end_date <= start_date:
            raise ValidationError({"end_date": ["Дата окончания договора должна быть позже даты начала"]})


class UpdateContractSchema(BaseSchema):
    start_date = DateField(allow_none=True)
    end_date = DateField(allow_none=True)
    term_years = fields.Float(allow_none=True)
    notes = fields.Str(allow_none=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date and end_date and end_date <= start_date:
            raise ValidationError({"end_date": ["Дата окончания договора должна быть позже даты начала"]})


class CreatePassportSchema(BaseSchema):
    person_id = fields.Int(required=True)
    valid_until = DateField(required=True)
    series_number = fields.Str(allow_none=True)


class UpdatePassportSchema(BaseSchema):
    received_date = DateField(allow_none=True)


class UpdateTenureAwardSchema(BaseSchema):
    is_received = fields.Bool()
    received_date = DateField(allow_none=True)


class NotificationRuleSchema(BaseSchema):
    room_token = fields.Str(required=True, validate=validate.Length(min=1, max=128))
    room_name = fields.Str(allow_none=True)
    event_type = fields.Str(allow_none=True)
    is_enabled = fields.Bool(load_default=True)
    remind_days_before = fields.Int(load_default=0)
    repeat_interval_days = fields.Int(load_default=7)
    overdue_interval_days = fields.Int(load_default=3)
    escalation_room_token = fields.Str(allow_none=True)
    escalation_after_days = fields.Int(allow_none=True)
    send_time_moscow = fields.Str(load_default="09:00")


class NotificationTestSchema(BaseSchema):
    room_token = fields.Str(required=True)
    message = fields.Str(load_default="Тестовое уведомление Bookuchet")


class ImportConfirmSchema(BaseSchema):
    row_actions = fields.Dict(keys=fields.Raw(), values=fields.Raw(), load_default=dict)
    mark_reached_tenure = fields.Bool(load_default=True)
    update_existing_tenure = fields.Bool(load_default=True)


class LoginSchema(BaseSchema):
    username = fields.Str(required=True, validate=validate.Length(min=1, max=64))
    password = fields.Str(required=True, validate=validate.Length(min=1))


def parse_query_date(value: str | None, *, field_name: str = "date") -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field_name: ["Invalid date format, expected YYYY-MM-DD"]}) from exc


def validate_role_name(value: str) -> str:
    try:
        RoleName(value)
    except ValueError as exc:
        raise ValidationError({"role": [f"Invalid role: {value}"]}) from exc
    return value
