"""Dashboard statistics aggregation."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from app.models import (
    EmployeeGradeHistory,
    Employment,
    EmploymentStatus,
    Event,
    EventStatus,
    TenureAward,
)
from app.services.employees import get_active_contract, get_active_passport, get_current_grade
from app.services.passports import compute_passport_status
from app.utils.dates import today_moscow


def _default_period(reference: date | None = None) -> tuple[date, date]:
    today = reference or today_moscow()
    date_from = today - relativedelta(months=12)
    return date_from, today


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _employment_ids(company_id: int) -> list[int]:
    rows = Employment.query.filter_by(company_id=company_id).all()
    return [row.id for row in rows]


def build_dashboard_stats(
    company_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    reference: date | None = None,
) -> dict:
    today = reference or today_moscow()
    if date_from is None or date_to is None:
        date_from, date_to = _default_period(today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    employment_ids = _employment_ids(company_id)
    active_employments = Employment.query.filter_by(
        company_id=company_id,
        status=EmploymentStatus.ACTIVE.value,
    ).all()

    hired_in_period = Employment.query.filter(
        Employment.company_id == company_id,
        Employment.hire_date >= date_from,
        Employment.hire_date <= date_to,
    ).count()
    dismissed_in_period = Employment.query.filter(
        Employment.company_id == company_id,
        Employment.dismissal_date.isnot(None),
        Employment.dismissal_date >= date_from,
        Employment.dismissal_date <= date_to,
    ).count()

    events_query = Event.query.filter(
        Event.company_id == company_id,
        Event.event_date >= date_from,
        Event.event_date <= date_to,
    )
    events = events_query.all()
    status_counts = Counter(event.status for event in events)
    type_counts = Counter(event.event_type for event in events)
    completed = status_counts.get(EventStatus.COMPLETED.value, 0)
    actionable = completed + status_counts.get(EventStatus.PLANNED.value, 0) + status_counts.get(
        EventStatus.OVERDUE.value, 0
    )
    completion_rate = round((completed / actionable) * 100, 1) if actionable else 0.0

    monthly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for event in events:
        key = _month_key(event.event_date)
        monthly[key]["total"] += 1
        monthly[key][event.status] += 1
    monthly_series = [
        {
            "month": month,
            "total": counts["total"],
            "planned": counts.get(EventStatus.PLANNED.value, 0),
            "overdue": counts.get(EventStatus.OVERDUE.value, 0),
            "completed": counts.get(EventStatus.COMPLETED.value, 0),
            "cancelled": counts.get(EventStatus.CANCELLED.value, 0),
        }
        for month, counts in sorted(monthly.items())
    ]

    active_contracts = 0
    expired_contracts = 0
    expiring_120 = 0
    for employment in active_employments:
        contract = get_active_contract(employment)
        if not contract:
            continue
        active_contracts += 1
        days_left = (contract.end_date - today).days
        if days_left < 0:
            expired_contracts += 1
        elif days_left <= 120:
            expiring_120 += 1

    grade_distribution: Counter[str] = Counter()
    eligible_now = 0
    eligible_30 = 0
    without_grade = 0
    for employment in active_employments:
        grade = get_current_grade(employment)
        if not grade:
            without_grade += 1
            continue
        grade_distribution[grade.grade.name] += 1
        eligible_date = grade.assigned_date + relativedelta(months=grade.grade.min_months)
        days_left = (eligible_date - today).days
        if days_left <= 0:
            eligible_now += 1
        elif days_left <= 30:
            eligible_30 += 1

    tenure_pending = {10: 0, 15: 0, 20: 0}
    tenure_received = {10: 0, 15: 0, 20: 0}
    if employment_ids:
        awards = TenureAward.query.filter(TenureAward.employment_id.in_(employment_ids)).all()
        for award in awards:
            if award.milestone_years not in tenure_pending:
                continue
            if award.is_received:
                tenure_received[award.milestone_years] += 1
            else:
                tenure_pending[award.milestone_years] += 1

    passport_counts = {"ok": 0, "requires_preparation": 0, "expired": 0, "missing": 0}
    expiring_90 = 0
    for employment in active_employments:
        passport = get_active_passport(employment.person)
        if not passport:
            passport_counts["missing"] += 1
            continue
        status = compute_passport_status(passport.valid_until, today)
        passport_counts[status] += 1
        days_left = (passport.valid_until - today).days
        if 0 <= days_left <= 90:
            expiring_90 += 1

    grades_assigned = 0
    if employment_ids:
        grades_assigned = EmployeeGradeHistory.query.filter(
            EmployeeGradeHistory.employment_id.in_(employment_ids),
            EmployeeGradeHistory.assigned_date >= date_from,
            EmployeeGradeHistory.assigned_date <= date_to,
        ).count()

    awards_received = 0
    if employment_ids:
        awards_received = TenureAward.query.filter(
            TenureAward.employment_id.in_(employment_ids),
            TenureAward.is_received.is_(True),
            TenureAward.received_date.isnot(None),
            TenureAward.received_date >= date_from,
            TenureAward.received_date <= date_to,
        ).count()

    return {
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        },
        "employees": {
            "active": len(active_employments),
            "hired_in_period": hired_in_period,
            "dismissed_in_period": dismissed_in_period,
        },
        "events": {
            "planned": status_counts.get(EventStatus.PLANNED.value, 0),
            "overdue": status_counts.get(EventStatus.OVERDUE.value, 0),
            "completed": completed,
            "cancelled": status_counts.get(EventStatus.CANCELLED.value, 0),
            "completion_rate": completion_rate,
            "by_type": dict(type_counts),
            "monthly": monthly_series,
        },
        "contracts": {
            "active": active_contracts,
            "expired": expired_contracts,
            "expiring_120d": expiring_120,
        },
        "grades": {
            "distribution": dict(grade_distribution),
            "without_grade": without_grade,
            "eligible_now": eligible_now,
            "eligible_30d": eligible_30,
            "assigned_in_period": grades_assigned,
        },
        "tenure": {
            "pending": {str(k): v for k, v in tenure_pending.items()},
            "received": {str(k): v for k, v in tenure_received.items()},
            "received_in_period": awards_received,
        },
        "passports": {
            **passport_counts,
            "expiring_90d": expiring_90,
        },
    }
