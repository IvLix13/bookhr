"""Domain changes applied when an event is completed.

Completing an event is not only a status change: a finished grade review has to
actually promote the employee, and every completion has to refresh the rule
events of that employment so the dashboards stop showing stale work.
"""

from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import Contract, EmployeeGradeHistory, Event, EventType
from app.services.audit import _current_user_id, log_audit
from app.services.employees import get_active_contract, get_current_grade
from app.services.grades import assign_grade_to_employment, compute_grade_eligibility
from app.services.rule_engine import recalculate_employment_events
from app.utils.dates import calculate_contract_end, today_moscow


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


def _extend_contract_after_report_completion(
    event: Event,
    term_years: float | None = None,
    new_end_date: date | None = None,
) -> Contract | None:
    """Extend the contract when the renewal report event is completed with an extension term."""
    if term_years is None and new_end_date is None:
        return None

    employment = event.employment
    if not employment:
        return None

    contract = None
    if event.reference_type == "contract" and event.reference_id:
        contract = db.session.get(Contract, event.reference_id)
    if not contract:
        contract = get_active_contract(employment)
    if not contract:
        return None

    old_end_date = contract.end_date
    if new_end_date is not None:
        target_end_date = new_end_date
    elif term_years is not None:
        target_end_date = calculate_contract_end(contract.end_date, term_years)
        contract.term_years = term_years
    else:
        return None

    contract.end_date = target_end_date
    contract.is_active = True

    log_audit(
        "contract_extend",
        "contract",
        contract.id,
        {"end_date": old_end_date.isoformat()},
        {
            "end_date": target_end_date.isoformat(),
            "term_years": contract.term_years,
            "event_id": event.id,
        },
    )
    return contract


def apply_completion_effects(
    event: Event,
    term_years: float | None = None,
    new_end_date: date | None = None,
) -> dict:
    """Apply the domain side effects implied by completing ``event``."""
    assigned_grade = None
    extended_contract = None
    if event.event_type == EventType.GRADE.value:
        assigned_grade = _promote_after_grade_review(event)
    elif (
        event.event_type == EventType.REPORT.value
        and event.reference_type == "contract"
    ):
        extended_contract = _extend_contract_after_report_completion(
            event,
            term_years=term_years,
            new_end_date=new_end_date,
        )

    if event.employment:
        recalculate_employment_events(event.employment)

    return {
        "assigned_grade": assigned_grade,
        "extended_contract": extended_contract,
    }
