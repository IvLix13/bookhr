"""Server-side calendar scope. Uses local database fields only."""
from flask_login import current_user
from sqlalchemy import false
from app.models import Employment, Event
from app.extensions import db
from app.services.departments import department_key, company_employments


def calendar_access(user):
    if user.role_name != "viewer":
        return {"available": True, "department": None, "reason": None}
    employment = db.session.get(Employment, user.employment_id) if user.employment_id else None
    if not employment or employment.company_id != user.company_id or employment.status != "active":
        return {"available": False, "department": None, "reason": "employment_missing"}
    key = department_key(employment)
    return {"available": bool(key), "department": employment.formal_department_short_name,
            "reason": None if key else "department_missing"}


def visible_events(query):
    query = query.filter(Event.company_id == current_user.company_id)
    if current_user.role_name != "viewer":
        return query
    if not calendar_access(current_user)["available"]:
        return query.filter(false())
    key = department_key(db.session.get(Employment, current_user.employment_id))
    ids = [e.id for e in company_employments(current_user.company_id) if department_key(e) == key]
    return query.filter(Event.employment_id.in_(ids))
