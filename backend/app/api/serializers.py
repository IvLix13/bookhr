"""Serializers for API responses."""

from __future__ import annotations

from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    Event,
    EventType,
    GradeCatalog,
    ImportJob,
    NotificationRule,
    Passport,
    Person,
    Reward,
    Role,
    TenureAward,
    User,
)
from app.services.employees import (
    get_active_contract,
    get_active_passport,
    get_current_grade,
    get_current_name,
    get_current_position,
)
from app.services.events import effective_event_status
from app.services.grade_catalog import grade_usage_employment_ids
from app.services.grades import compute_grade_eligibility
from app.services.passports import compute_passport_status, passport_days_left
from app.services.rule_engine import find_contract_renewal_event
from app.services.tenure import tenure_years
from app.utils.dates import today_moscow


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role_name,
        "company_id": user.company_id,
        "must_change_password": user.must_change_password,
    }


def role_to_dict(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
    }


def user_admin_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role_name,
        "auth_source": user.auth_source,
        "is_active": user.is_active,
        "is_locked": user.is_locked(),
        "failed_login_attempts": user.failed_login_attempts,
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def grade_to_dict(grade: GradeCatalog, *, include_usage: bool = False) -> dict:
    payload = {
        "id": grade.id,
        "name": grade.name,
        "rank": grade.rank,
        "min_years": float(grade.min_years),
        "extra_year_without_university": grade.extra_year_without_university,
        "is_active": grade.is_active,
    }
    if include_usage:
        payload["in_use_count"] = len(grade_usage_employment_ids(grade.id))
    return payload


def employment_to_dict(employment: Employment) -> dict:
    person = employment.person
    position = get_current_position(employment)
    grade = get_current_grade(employment)
    contract = get_active_contract(employment)
    passport = get_active_passport(person)
    today = today_moscow()
    eligibility = compute_grade_eligibility(employment, today)
    latest_reward = _latest_reward(employment)

    return {
        "id": employment.id,
        "person_uuid": str(person.uuid),
        "full_name": get_current_name(person),
        "title": position.title if position else None,
        "position_grade": grade_to_dict(position.position_grade)
        if position and position.position_grade
        else None,
        "actual_grade": grade_to_dict(grade.grade) if grade else None,
        "grade_date": grade.assigned_date.isoformat() if grade else None,
        "eligible_date": eligibility["eligible_date"].isoformat()
        if eligibility["eligible_date"]
        else None,
        "education_status": person.education_status,
        "hire_date": employment.hire_date.isoformat(),
        "status": employment.status,
        "contract_end": contract.end_date.isoformat() if contract else None,
        "contract_term_years": contract.term_years if contract else None,
        "contract_days_left": (contract.end_date - today).days if contract else None,
        "passport_until": passport.valid_until.isoformat() if passport else None,
        "passport_status": compute_passport_status(passport.valid_until)
        if passport
        else None,
        "passport_days_left": passport_days_left(passport.valid_until) if passport else None,
        "tenure_years": tenure_years(employment.hire_date, today),
        "reward_status": latest_reward.status if latest_reward else None,
    }


def _latest_reward(employment: Employment) -> Reward | None:
    rewards = list(employment.rewards)
    if not rewards:
        return None
    return max(rewards, key=lambda reward: (reward.updated_at, reward.id))


def contract_to_dict(contract: Contract) -> dict:
    today = today_moscow()
    employment = contract.employment
    renewal_event = find_contract_renewal_event(contract.id)
    return {
        "id": contract.id,
        "employment_id": contract.employment_id,
        "full_name": get_current_name(employment.person),
        "start_date": contract.start_date.isoformat(),
        "end_date": contract.end_date.isoformat(),
        "term_years": contract.term_years,
        "days_left": (contract.end_date - today).days,
        "is_active": contract.is_active,
        "renewal_report_event": {
            "id": renewal_event.id,
            "event_date": renewal_event.event_date.isoformat(),
            "completed_date": renewal_event.completed_at.date().isoformat()
            if renewal_event.completed_at
            else None,
            "status": renewal_event.status,
            "effective_status": effective_event_status(renewal_event, today),
        }
        if renewal_event
        else None,
    }


def grade_row_to_dict(employment: Employment) -> dict:
    grade = get_current_grade(employment)
    eligibility = compute_grade_eligibility(employment)

    return {
        "employment_id": employment.id,
        "full_name": get_current_name(employment.person),
        "grade": grade_to_dict(grade.grade) if grade else None,
        "grade_date": grade.assigned_date.isoformat() if grade else None,
        "next_grade": grade_to_dict(eligibility["next_grade"])
        if eligibility["next_grade"]
        else None,
        "next_rank": eligibility["next_rank"],
        "next_grade_candidates": [
            grade_to_dict(candidate)
            for candidate in eligibility["next_grade_candidates"]
        ],
        "requires_grade_choice": eligibility["requires_grade_choice"],
        "blocked_reason": eligibility["blocked_reason"],
        "eligible_date": eligibility["eligible_date"].isoformat()
        if eligibility["eligible_date"]
        else None,
        "days_left": eligibility["days_left"],
        "is_available": eligibility["is_available"],
    }


def passport_row_to_dict(person: Person, employment: Employment | None = None) -> dict:
    passport = get_active_passport(person)
    today = today_moscow()
    return {
        "person_uuid": str(person.uuid),
        "employment_id": employment.id if employment else None,
        "full_name": get_current_name(person),
        "valid_until": passport.valid_until.isoformat() if passport else None,
        "days_left": passport_days_left(passport.valid_until, today) if passport else None,
        "status": compute_passport_status(passport.valid_until, today) if passport else None,
    }


def tenure_row_to_dict(employment: Employment) -> dict:
    awards = TenureAward.query.filter_by(employment_id=employment.id).all()
    award_map = {a.milestone_years: a for a in awards}
    return {
        "employment_id": employment.id,
        "full_name": get_current_name(employment.person),
        "tenure_years": tenure_years(employment.hire_date),
        "awards": {
            str(years): {
                "milestone_years": years,
                "milestone_date": award_map[years].milestone_date.isoformat()
                if years in award_map
                else None,
                "is_received": award_map[years].is_received if years in award_map else False,
            }
            for years in (10, 15, 20)
        },
    }


def reward_to_dict(reward: Reward) -> dict:
    return {
        "id": reward.id,
        "employment_id": reward.employment_id,
        "full_name": get_current_name(reward.employment.person),
        "reward_type": reward.reward_type,
        "status": reward.status,
        "directive_text": reward.directive_text,
        "delivered_date": reward.delivered_date.isoformat() if reward.delivered_date else None,
        "notes": reward.notes,
        "updated_at": reward.updated_at.isoformat() if reward.updated_at else None,
    }


def event_to_dict(event: Event) -> dict:
    grade_completion = None
    if event.event_type == EventType.GRADE.value and event.employment:
        eligibility = compute_grade_eligibility(event.employment)
        grade_completion = {
            "next_rank": eligibility["next_rank"],
            "candidates": [
                grade_to_dict(candidate)
                for candidate in eligibility["next_grade_candidates"]
            ],
            "requires_selection": eligibility["requires_grade_choice"],
            "eligible_date": eligibility["eligible_date"].isoformat()
            if eligibility["eligible_date"]
            else None,
            "blocked_reason": eligibility["blocked_reason"],
        }

    return {
        "id": event.id,
        "title": event.title,
        "event_type": event.event_type,
        "description": event.description,
        "event_date": event.event_date.isoformat(),
        "status": event.status,
        "effective_status": effective_event_status(event),
        "source": event.source,
        "employment_id": event.employment_id,
        "reference_type": event.reference_type,
        "reference_id": event.reference_id,
        "employee_name": get_current_name(event.employment.person)
        if event.employment
        else None,
        "created_by": event.created_by.full_name if event.created_by else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "completed_at": event.completed_at.isoformat() if event.completed_at else None,
        "completion_comment": event.completion_comment,
        "grade_completion": grade_completion,
    }


def import_job_to_dict(job: ImportJob) -> dict:
    raw_summary = job.summary
    summary = raw_summary
    unknown_grades: list[dict] = []
    if isinstance(raw_summary, dict):
        unknown_grades = list(raw_summary.get("unknown_grades") or [])
        summary = {key: value for key, value in raw_summary.items() if key != "unknown_grades"}
    return {
        "id": job.id,
        "filename": job.filename,
        "import_type": job.import_type,
        "status": job.status,
        "summary": summary,
        "unknown_grades": unknown_grades,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "rows": [
            {
                "id": row.id,
                "row_number": row.row_number,
                "action": row.action,
                "person_uuid": str(row.person_uuid) if row.person_uuid else None,
                "candidates": row.candidates,
                "errors": row.errors,
                "warnings": row.warnings,
                "result": row.result,
                "result_message": row.result_message,
                "full_name": (row.raw_data or {}).get("full_name"),
                "reward_type": (row.raw_data or {}).get("reward_type"),
            }
            for row in job.rows
        ],
    }


def notification_rule_to_dict(rule: NotificationRule) -> dict:
    return {
        "id": rule.id,
        "company_id": rule.company_id,
        "event_type": rule.event_type,
        "room_token": rule.room_token,
        "room_name": rule.room_name,
        "is_enabled": rule.is_enabled,
        "remind_days_before": rule.remind_days_before,
        "repeat_interval_days": rule.repeat_interval_days,
        "overdue_interval_days": rule.overdue_interval_days,
        "escalation_room_token": rule.escalation_room_token,
        "escalation_after_days": rule.escalation_after_days,
        "send_time_moscow": rule.send_time_moscow,
    }
