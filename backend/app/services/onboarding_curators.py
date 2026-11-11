"""Resolve a plan's mentor locally, retaining explicit wizard selections."""

from app.extensions import db
from app.models import Employment
from app.services.department_heads import get_current_name
from app.services.departments import company_employments


def normalized_name(name):
    return " ".join((name or "").split()).casefold()


def matching_curator(employee, name, *, employment_ids=None):
    """Support old text-only plans using an unambiguous full current name."""
    target = normalized_name(name)
    if not target:
        return None
    matches = [
        row for row in company_employments(employee.company_id)
        if row.status == "active" and row.person_id != employee.person_id
        and (employment_ids is None or row.id in employment_ids)
        and normalized_name(get_current_name(row.person)) == target
    ]
    return matches[0] if len(matches) == 1 else None


def curator_for_plan(plan):
    curator_id = getattr(plan, "curator_employment_id", None)
    if curator_id is None:
        return matching_curator(plan.employment, plan.curator_name)
    curator = db.session.get(Employment, curator_id)
    if (curator is None or curator.company_id != plan.employment.company_id
            or curator.person_id == plan.employment.person_id):
        return None
    return curator
