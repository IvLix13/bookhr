"""Tenure award service."""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import Employment, EmploymentStatus, TenureAward
from app.utils.dates import today_moscow

MILESTONES = (10, 15, 20)
MAX_EMPLOYMENT_PERIODS = 3


def employment_periods(person_id: int, company_id: int) -> list[Employment]:
    return (
        Employment.query.filter_by(person_id=person_id, company_id=company_id)
        .order_by(Employment.hire_date.asc(), Employment.id.asc())
        .all()
    )


def count_employment_periods(person_id: int, company_id: int) -> int:
    return Employment.query.filter_by(person_id=person_id, company_id=company_id).count()


def tenure_years(hire_date: date, reference: date | None = None) -> int:
    ref = reference or today_moscow()
    delta = relativedelta(ref, hire_date)
    return delta.years


def _months_between(start: date, end: date) -> int:
    delta = relativedelta(end, start)
    return delta.years * 12 + delta.months


def _period_end(employment: Employment, reference: date) -> date:
    if employment.dismissal_date and employment.dismissal_date <= reference:
        return employment.dismissal_date
    return reference


def total_tenure_years(
    person_id: int,
    company_id: int,
    reference: date | None = None,
) -> int:
    ref = reference or today_moscow()
    total_months = 0
    for employment in employment_periods(person_id, company_id):
        if employment.hire_date > ref:
            continue
        end = _period_end(employment, ref)
        total_months += _months_between(employment.hire_date, end)
    return total_months // 12


def compute_milestone_date(
    person_id: int,
    company_id: int,
    milestone_years: int,
) -> date:
    """Date when cumulative tenure across all periods reaches ``milestone_years``.

    Sums actual worked months in each employment period (same basis as
    ``total_tenure_years``), skipping calendar gaps between periods.
    """
    periods = employment_periods(person_id, company_id)
    if not periods:
        raise ValueError("No employment periods found")

    remaining_months = milestone_years * 12
    for employment in periods:
        if employment.dismissal_date:
            period_months = _months_between(
                employment.hire_date,
                employment.dismissal_date,
            )
            if period_months >= remaining_months:
                return employment.hire_date + relativedelta(months=remaining_months)
            remaining_months -= period_months
            continue

        return employment.hire_date + relativedelta(months=remaining_months)

    last = periods[-1]
    return last.hire_date + relativedelta(months=remaining_months)


def active_employment(person_id: int, company_id: int) -> Employment | None:
    return (
        Employment.query.filter_by(
            person_id=person_id,
            company_id=company_id,
            status=EmploymentStatus.ACTIVE.value,
        )
        .order_by(Employment.hire_date.desc(), Employment.id.desc())
        .first()
    )


def continuous_tenure_years(
    person_id: int,
    company_id: int,
    reference: date | None = None,
) -> int:
    employment = active_employment(person_id, company_id)
    if not employment:
        return 0
    return tenure_years(employment.hire_date, reference)


def continuous_milestone_reached_date(
    person_id: int,
    company_id: int,
    milestone_years: int,
) -> date | None:
    """Date when the active employment period reaches ``milestone_years``."""
    employment = active_employment(person_id, company_id)
    if not employment:
        return None
    return employment.hire_date + relativedelta(years=milestone_years)


def is_tenure_award_auto_eligible(
    award: TenureAward,
    reference: date | None = None,
) -> bool:
    """Award can be granted automatically only on continuous active tenure."""
    if award.is_received:
        return False

    ref = reference or today_moscow()
    continuous = continuous_tenure_years(award.person_id, award.company_id, ref)
    if continuous < award.milestone_years:
        return False

    reached_on = continuous_milestone_reached_date(
        award.person_id,
        award.company_id,
        award.milestone_years,
    )
    return reached_on is not None and reached_on <= ref


def ensure_tenure_awards(person_id: int, company_id: int) -> list[TenureAward]:
    awards: list[TenureAward] = []
    for years in MILESTONES:
        existing = TenureAward.query.filter_by(
            person_id=person_id,
            company_id=company_id,
            milestone_years=years,
        ).first()
        milestone_date = compute_milestone_date(person_id, company_id, years)
        if existing:
            if not existing.is_received and existing.milestone_date != milestone_date:
                existing.milestone_date = milestone_date
            awards.append(existing)
            continue

        award = TenureAward(
            person_id=person_id,
            company_id=company_id,
            milestone_years=years,
            milestone_date=milestone_date,
            is_received=False,
        )
        db.session.add(award)
        awards.append(award)
    return awards


def auto_mark_reached_awards(
    awards: list[TenureAward],
    reference: date | None = None,
) -> int:
    """Mark tenure milestones when continuous active tenure reaches the milestone.

    ``milestone_date`` is still based on cumulative tenure across all periods and
    is shown to HR, but automatic receipt requires uninterrupted tenure in the
    current employment period.
    """
    ref = reference or today_moscow()
    marked = 0
    for award in awards:
        if not is_tenure_award_auto_eligible(award, ref):
            continue
        award.is_received = True
        if award.received_date is None:
            reached_on = continuous_milestone_reached_date(
                award.person_id,
                award.company_id,
                award.milestone_years,
            )
            award.received_date = reached_on or award.milestone_date
        marked += 1
    return marked
