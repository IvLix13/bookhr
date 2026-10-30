"""Resolve a department head from local placement and grade history."""
import re
from app.services.departments import department_key, company_employments
def get_current_position(employment):
    return max((p for p in employment.position_history if p.valid_to is None), key=lambda p: (p.valid_from, p.id), default=None)


def get_current_grade(employment):
    return max((g for g in employment.grade_history if g.valid_to is None), key=lambda g: (g.assigned_date, g.id), default=None)


def get_current_name(person):
    current = max((n for n in person.name_history if n.valid_to is None), key=lambda n: (n.valid_from, n.id), default=None)
    return current.full_name if current else None


def short_employee_name(employment):
    name = employment.person.fio_short or ""
    if re.fullmatch(r"\S+\s+[А-ЯA-ZЁ]\.\s*(?:[А-ЯA-ZЁ]\.)?", name.strip()):
        return re.sub(r"\.\s+", ".", name.strip())
    parts = (get_current_name(employment.person) or "").split()
    return parts[0] + (" " + "".join(p[0] + "." for p in parts[1:]) if len(parts)>1 else "") if parts else "—"


def head_values(employment):
    key = department_key(employment)
    if not key:
        return "department_missing", None
    candidates = []
    for row in company_employments(employment.company_id):
        if row.person_id == employment.person_id or row.status != "active" or department_key(row) != key:
            continue
        position = get_current_position(row)
        title = " ".join((position.title if position else "").split()).casefold()
        if re.match(r"^начальник отдела(?:\W|$)", title):
            candidates.append(row)
    if len(candidates) != 1:
        return ("ambiguous" if candidates else "not_found"), None
    row = candidates[0]
    grade = get_current_grade(row)
    return "found", {"employment_id": row.id, "short_name": short_employee_name(row),
                     "position": get_current_position(row).title,
                     "grade": grade.grade.name if grade else None}
