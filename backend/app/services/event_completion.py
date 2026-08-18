"""Domain changes applied when an event is completed.

Completing an event is not only a status change: a finished grade review has to
actually promote the employee, and every completion has to refresh the rule
events of that employment so the dashboards stop showing stale work.
"""

from __future__ import annotations

from datetime import date

from app.extensions import db
from app.models import Contract, EmployeeGradeHistory, Event, EventStatus, EventType, Passport
from app.services.audit import _current_user_id, log_audit
from app.services.employees import get_active_contract, get_active_passport, get_current_grade
from app.services.grades import assign_grade_to_employment, compute_grade_eligibility
from app.services.rule_engine import (
    grade_preparation_rule_key,
    is_grade_preparation_event,
    is_grade_promotion_event,
    is_passport_preparation_event,
    recalculate_employment_events,
)
from app.utils.dates import calculate_contract_end, today_moscow


def grade_promotion_blocked_reason(event: Event) -> str | None:
    """Return a user-facing reason when promotion must wait for preparation."""
    if not is_grade_promotion_event(event) or not event.rule_key or not event.employment:
        return None

    eligibility = compute_grade_eligibility(event.employment)
    if eligibility["blocked_reason"]:
        return eligibility["blocked_reason"]

    eligible_date = eligibility["eligible_date"]
    grade_history_id = event.reference_id
    if eligible_date is None or grade_history_id is None:
        return None

    if not _grade_preparation_completed(event, grade_history_id, eligible_date):
        return "Сначала выполните подготовку документов на повышение грейда"
    return None


def _grade_preparation_completed(
    event: Event,
    grade_history_id: int,
    eligible_date: date,
) -> bool:
    prep_key = grade_preparation_rule_key(grade_history_id, eligible_date)
    prep_event = Event.query.filter_by(rule_key=prep_key).first()
    if prep_event is None:
        return True
    return prep_event.status == EventStatus.COMPLETED.value


def _promote_after_grade_review(
    event: Event,
    target_grade_id: int | None = None,
) -> EmployeeGradeHistory | None:
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
    if eligibility["blocked_reason"]:
        raise ValueError(eligibility["blocked_reason"])
    candidates = eligibility["next_grade_candidates"]
    eligible_date = eligibility["eligible_date"]
    if not candidates or not eligible_date:
        return None

    if event.rule_key and not _grade_preparation_completed(
        event,
        current.id,
        eligible_date,
    ):
        raise ValueError(
            "Сначала выполните подготовку документов на повышение грейда"
        )

    if len(candidates) > 1 and target_grade_id is None:
        raise ValueError("Выберите следующий грейд")

    if target_grade_id is None:
        next_grade = candidates[0]
    else:
        next_grade = next(
            (grade for grade in candidates if grade.id == target_grade_id),
            None,
        )
        if next_grade is None:
            raise ValueError("Выбранный грейд больше недоступен")

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


def _renew_passport_after_preparation(
    event: Event,
    new_valid_until: date,
) -> Passport:
    """Register a renewed passport when preparation is completed."""
    employment = event.employment
    if not employment:
        raise ValueError("Мероприятие не привязано к сотруднику")

    today = today_moscow()
    if new_valid_until <= today:
        raise ValueError("Новый срок паспорта должен быть в будущем")

    person = employment.person
    active = get_active_passport(person)
    if active and new_valid_until <= active.valid_until:
        raise ValueError("Новый срок паспорта должен быть позже текущего")

    old_valid_until = active.valid_until.isoformat() if active else None
    if active:
        active.is_active = False

    passport = Passport(
        person_id=person.id,
        valid_until=new_valid_until,
        series_number=active.series_number if active else None,
        is_active=True,
    )
    db.session.add(passport)
    db.session.flush()

    log_audit(
        "passport_renew",
        "passport",
        passport.id,
        {"valid_until": old_valid_until},
        {
            "valid_until": new_valid_until.isoformat(),
            "event_id": event.id,
        },
    )
    return passport


def apply_completion_effects(
    event: Event,
    term_years: float | None = None,
    new_end_date: date | None = None,
    target_grade_id: int | None = None,
    new_passport_valid_until: date | None = None,
) -> dict:
    """Apply the domain side effects implied by completing ``event``."""
    assigned_grade = None
    extended_contract = None
    renewed_passport = None
    if event.event_type == EventType.GRADE.value:
        if is_grade_preparation_event(event):
            assigned_grade = None
        elif is_grade_promotion_event(event):
            assigned_grade = _promote_after_grade_review(
                event,
                target_grade_id=target_grade_id,
            )
        else:
            assigned_grade = _promote_after_grade_review(
                event,
                target_grade_id=target_grade_id,
            )
    elif (
        event.event_type == EventType.REPORT.value
        and event.reference_type == "contract"
    ):
        extended_contract = _extend_contract_after_report_completion(
            event,
            term_years=term_years,
            new_end_date=new_end_date,
        )
    elif is_passport_preparation_event(event):
        if new_passport_valid_until is None:
            raise ValueError("Укажите новый срок действия паспорта")
        renewed_passport = _renew_passport_after_preparation(
            event,
            new_passport_valid_until,
        )

    if event.employment:
        recalculate_employment_events(event.employment)

    return {
        "assigned_grade": assigned_grade,
        "extended_contract": extended_contract,
        "renewed_passport": renewed_passport,
    }
