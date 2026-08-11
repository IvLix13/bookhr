"""Serializers for API responses."""

from __future__ import annotations

from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    Event,
    GradeCatalog,
    ImportJob,
    NotificationRule,
    Passport,
    Person,
    Reward,
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
    }


def grade_to_dict(grade: GradeCatalog) -> dict:
    return {
        "id": grade.id,
        "name": grade.name,
        "rank": grade.rank,
        "min_months": grade.min_months,
        "is_active": grade.is_active,
    }


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
        "has_university": person.has_university,
        "hire_date": employment.hire_date.isoformat(),
        "status": employment.status,
        "contract_end": contract.end_date.isoformat() if contract else None,
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
        "days_left": (contract.end_date - today).days,
        "is_active": contract.is_active,
        "renewal_report_event": {
            "id": renewal_event.id,
            "event_date": renewal_event.event_date.isoformat(),
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
        "eligible_date": eligibility["eligible_date"].isoformat()
        if eligibility["eligible_date"]
        else None,
        "days_left": eligibility["days_left"],
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
    }


def import_job_to_dict(job: ImportJob) -> dict:
    return {
        "id": job.id,
        "filename": job.filename,
        "status": job.status,
        "summary": job.summary,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "rows": [
            {
                "id": row.id,
                "row_number": row.row_number,
                "action": row.action,
                "person_uuid": str(row.person_uuid) if row.person_uuid else None,
                "errors": row.errors,
                "warnings": row.warnings,
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
