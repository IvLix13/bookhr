"""Domain changes applied when an event is completed.

Completing an event is not only a status change: a finished grade review has to
actually promote the employee, and every completion has to refresh the rule
events of that employment so the dashboards stop showing stale work.
"""

from __future__ import annotations

from datetime import date

from app.models import EmployeeGradeHistory, Event, EventType
from app.services.audit import _current_user_id, log_audit
from app.services.employees import get_current_grade
from app.services.grades import assign_grade_to_employment, compute_grade_eligibility
from app.services.rule_engine import recalculate_employment_events
from app.utils.dates import today_moscow


def _promote_after_grade_review(event: Event) -> EmployeeGradeHistory | None:
    """Move the employee to the next grade once the review is done."""
    employment = event.employment
    if not employment:
        return None

    current = get_current_grade(employment)
    if not current:
        return None

    # A rule event points at the grade record it was created for. If that record
    # is no longer the open one the grade already moved on, so completing an old
    # event must not promote again.
    if (
        event.reference_type == "employee_grade_history"
        and event.reference_id is not None
        and event.reference_id != current.id
    ):
        return None

    eligibility = compute_grade_eligibility(employment)
    next_grade = eligibility["next_grade"]
    eligible_date = eligibility["eligible_date"]
    if not next_grade or not eligible_date:
        return None

    # The grade may not start before the employee is actually eligible, even
    # when the review is completed ahead of the due date.
    assigned_date: date = max(today_moscow(), eligible_date)
    reviewed_grade_id = current.id
    history = assign_grade_to_employment(
        employment,
        next_grade,
        assigned_date,
        basis=f"Мероприятие «{event.title}» выполнено",
        assigned_by_id=_current_user_id(),
    )
    # Record which grade record was reviewed so reopening and completing the
    # event again cannot promote the employee twice.
    event.reference_type = "employee_grade_history"
    event.reference_id = reviewed_grade_id
    log_audit(
        "grade_assign",
        "employee_grade_history",
        history.id,
        {"grade_id": current.grade_id},
        {
            "grade_id": next_grade.id,
            "assigned_date": assigned_date.isoformat(),
            "event_id": event.id,
        },
    )
    return history


def apply_completion_effects(event: Event) -> dict:
    """Apply the domain side effects implied by completing ``event``."""
    assigned_grade = None
    if event.event_type == EventType.GRADE.value:
        assigned_grade = _promote_after_grade_review(event)

    if event.employment:
        recalculate_employment_events(event.employment)

    return {"assigned_grade": assigned_grade}
