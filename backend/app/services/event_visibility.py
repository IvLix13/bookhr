"""Server-side calendar scope. Uses local database fields only."""
from flask_login import current_user
from app.models import Event
from app.services.departments import department_key, viewer_department_employment_ids, viewer_employment


def calendar_access(user):
    if user.role_name != "viewer":
        return {"available": True, "department": None, "reason": None}
    employment = viewer_employment(user)
    if employment is None:
        return {"available": False, "department": None, "reason": "employment_missing"}
    key = department_key(employment)
    return {"available": bool(key), "department": employment.formal_department_short_name,
            "reason": None if key else "department_missing"}


def visible_events(query):
    query = query.filter(Event.company_id == current_user.company_id)
    if current_user.role_name != "viewer":
        return query
    return query.filter(Event.employment_id.in_(viewer_department_employment_ids(current_user)))
