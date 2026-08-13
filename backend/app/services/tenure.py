"""Tenure award service."""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import TenureAward
from app.utils.dates import today_moscow

MILESTONES = (10, 15, 20)


def ensure_tenure_awards(employment_id: int, hire_date: date) -> list[TenureAward]:
    awards: list[TenureAward] = []
    for years in MILESTONES:
        existing = TenureAward.query.filter_by(
            employment_id=employment_id,
            milestone_years=years,
        ).first()
        if existing:
            awards.append(existing)
            continue

        milestone_date = hire_date + relativedelta(years=years)
        award = TenureAward(
            employment_id=employment_id,
            milestone_years=years,
            milestone_date=milestone_date,
            is_received=False,
        )
        db.session.add(award)
        awards.append(award)
    return awards


def tenure_years(hire_date: date, reference: date | None = None) -> int:
    ref = reference or today_moscow()
    delta = relativedelta(ref, hire_date)
    return delta.years


def auto_mark_reached_awards(
    awards: list[TenureAward],
    reference: date | None = None,
) -> int:
    """Mark tenure milestones already reached as received.

    Only awards that are not yet received are touched, so manual HR decisions
    (and already-received milestones) are preserved. The receipt date is set to
    the milestone date — the moment the employee earned it.
    """
    ref = reference or today_moscow()
    marked = 0
    for award in awards:
        if award.is_received:
            continue
        if award.milestone_date <= ref:
            award.is_received = True
            if award.received_date is None:
                award.received_date = award.milestone_date
            marked += 1
    return marked
