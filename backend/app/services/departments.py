"""Local formal department identity; never calls the directory service."""
from flask import request, has_request_context
from app.models import Employment, Person, EmployeeGradeHistory
from sqlalchemy.orm import selectinload


def department_key(employment):
    return " ".join((employment.formal_department_short_name or "").split()).casefold() or None


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
