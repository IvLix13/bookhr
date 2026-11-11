"""Local formal department identity; never calls the directory service."""
from flask import request, has_request_context
from app.extensions import db
from app.models import Employment, Person, EmployeeGradeHistory
from sqlalchemy.orm import selectinload


def _department_key(name):
    return " ".join((name or "").split()).casefold() or None


def department_key(employment):
    return _department_key(employment.formal_department_short_name)


def viewer_employment(user):
    employment = user.employment
    if employment and employment.company_id == user.company_id and employment.status == "active":
        return employment
    return None


def viewer_department_employment_ids(user):
    employment = viewer_employment(user)
    key = department_key(employment) if employment else None
    if key is None:
        return []
    rows = db.session.query(Employment.id, Employment.formal_department_short_name).filter(
        Employment.company_id == user.company_id,
        Employment.formal_department_short_name.is_not(None),
    )
    return [employment_id for employment_id, name in rows if _department_key(name) == key]


def company_employments(company_id):
    # Request-local cache only: transfers take effect on the next request.
    key = f"department_employments_{company_id}"
    if has_request_context() and hasattr(request, key):
        return getattr(request, key)
    rows = Employment.query.filter_by(company_id=company_id).options(
        selectinload(Employment.position_history),
        selectinload(Employment.grade_history).selectinload(EmployeeGradeHistory.grade),
        selectinload(Employment.person).selectinload(Person.name_history),
    ).all()
    if has_request_context():
        setattr(request, key, rows)
    return rows
