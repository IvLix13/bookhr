"""Tenure award service."""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import Employment, EmploymentStatus, TenureAward
from app.utils.dates import today_moscow

MILESTONES = (10, 15, 20)
LOWER_MILESTONES: dict[int, tuple[int, ...]] = {
    10: (),
    15: (10,),
    20: (10, 15),
}
MAX_EMPLOYMENT_PERIODS = 3
TENURE_AWARD_EVENT_HORIZON_YEARS = 3


def is_tenure_award_pending(
    award: TenureAward,
    person_awards: dict[int, TenureAward],
    reference: date | None = None,
) -> bool:
    """Pending for stats/attention: due date reached and all lower milestones received."""
    if award.is_received:
        return False

    ref = reference or today_moscow()
    if award.milestone_date > ref:
        return False

    for lower_years in LOWER_MILESTONES.get(award.milestone_years, ()):
        lower_award = person_awards.get(lower_years)
        if not lower_award or not lower_award.is_received:
            return False

    return True


def is_tenure_award_scheduled(
    award: TenureAward,
    person_awards: dict[int, TenureAward],
    reference: date | None = None,
    horizon_years: int = TENURE_AWARD_EVENT_HORIZON_YEARS,
) -> bool:
    """Eligible for rule-engine event: unreceived, lower milestones received, within horizon."""
    if award.is_received:
        return False

    ref = reference or today_moscow()
    horizon_end = ref + relativedelta(years=horizon_years)
    if award.milestone_date > horizon_end:
        return False

    for lower_years in LOWER_MILESTONES.get(award.milestone_years, ()):
        lower_award = person_awards.get(lower_years)
        if not lower_award or not lower_award.is_received:
            return False

    return True


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
    """Award can be granted automatically when cumulative tenure reaches the milestone."""
    if award.is_received:
        return False

    ref = reference or today_moscow()
    if award.milestone_date > ref:
        return False

    return total_tenure_years(award.person_id, award.company_id, ref) >= award.milestone_years


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
    if awards:
        db.session.flush()
    return awards


def auto_mark_reached_awards(
    awards: list[TenureAward],
    reference: date | None = None,
) -> int:
    """Mark tenure milestones when cumulative tenure reaches the milestone date."""
    ref = reference or today_moscow()
    by_years = {award.milestone_years: award for award in awards}
    marked = 0
    for award in awards:
        if not is_tenure_award_pending(award, by_years, ref):
            continue
        award.is_received = True
        if award.received_date is None:
            award.received_date = award.milestone_date
        marked += 1
    return marked
