"""Batch loading helpers for the tenure awards list."""

from __future__ import annotations

from collections import defaultdict

from app.models import Employment, PersonNameHistory, TenureAward
from app.services.tenure import MILESTONES, tenure_years, total_tenure_years_from_periods


def build_tenure_rows(
    employments: list[Employment],
) -> tuple[dict[int, dict], dict[int, int]]:
    """Serialize tenure rows without per-row period, award, or name queries."""
    if not employments:
        return {}, {}

    person_ids = {employment.person_id for employment in employments}
    company_ids = {employment.company_id for employment in employments}

    periods = (
        Employment.query.filter(
            Employment.person_id.in_(person_ids),
            Employment.company_id.in_(company_ids),
        )
        .order_by(
            Employment.person_id.asc(),
            Employment.company_id.asc(),
            Employment.hire_date.asc(),
            Employment.id.asc(),
        )
        .all()
    )
    periods_by_person: dict[tuple[int, int], list[Employment]] = defaultdict(list)
    for period in periods:
        periods_by_person[(period.person_id, period.company_id)].append(period)

    awards = TenureAward.query.filter(
        TenureAward.person_id.in_(person_ids),
        TenureAward.company_id.in_(company_ids),
    ).all()
    awards_by_person: dict[tuple[int, int], dict[int, TenureAward]] = defaultdict(dict)
    for award in awards:
        awards_by_person[(award.person_id, award.company_id)][award.milestone_years] = award

    names = (
        PersonNameHistory.query.filter(
            PersonNameHistory.person_id.in_(person_ids),
            PersonNameHistory.valid_to.is_(None),
        )
        .order_by(
            PersonNameHistory.person_id.asc(),
            PersonNameHistory.valid_from.desc(),
            PersonNameHistory.id.desc(),
        )
        .all()
    )
    names_by_person: dict[int, str | None] = {}
    for name in names:
        names_by_person.setdefault(name.person_id, name.full_name)

    rows: dict[int, dict] = {}
    totals: dict[int, int] = {}
    for employment in employments:
        key = (employment.person_id, employment.company_id)
        total_years = total_tenure_years_from_periods(periods_by_person.get(key, []))
        totals[employment.id] = total_years
        award_map = awards_by_person.get(key, {})
        rows[employment.id] = {
            "employment_id": employment.id,
            "full_name": names_by_person.get(employment.person_id),
            "tenure_years": total_years,
            "continuous_tenure_years": tenure_years(employment.hire_date),
            "awards": {
                str(years): {
                    "id": award_map[years].id if years in award_map else None,
                    "milestone_years": years,
                    "milestone_date": (
                        award_map[years].milestone_date.isoformat()
                        if years in award_map
                        else None
                    ),
                    "is_received": (
                        award_map[years].is_received if years in award_map else False
                    ),
                    "received_date": (
                        award_map[years].received_date.isoformat()
                        if years in award_map and award_map[years].received_date
                        else None
                    ),
                }
                for years in MILESTONES
            },
        }

    return rows, totals
