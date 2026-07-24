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
