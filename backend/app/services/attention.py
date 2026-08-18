"""Attention items for dashboard and navigation badges."""

from __future__ import annotations

from app.models import (
    EmployeeGradeHistory,
    Employment,
    EmploymentStatus,
    Event,
    EventStatus,
    EventType,
    TenureAward,
)
from app.services.employees import get_active_contract, get_active_passport, get_current_grade, get_current_name
from app.services.events import effectively_overdue_filter
from app.services.grades import compute_grade_eligibility
from app.services.passports import compute_passport_status
from app.services.tenure import active_employment, is_tenure_award_auto_eligible
from app.utils.dates import today_moscow

ALL_CATEGORIES = ("events", "contracts", "passports", "grades", "tenure")
_OPEN_EVENT_STATUSES = (EventStatus.PLANNED.value, EventStatus.OVERDUE.value)


def _open_event_for(*, company_id: int, employment_id: int, event_type: EventType) -> Event | None:
    return (
        Event.query.filter_by(
            company_id=company_id,
            employment_id=employment_id,
            event_type=event_type.value,
        )
        .filter(Event.status.in_(_OPEN_EVENT_STATUSES))
        .order_by(Event.event_date.asc(), Event.id.asc())
        .first()
    )


def _attention_item(
    *,
    category: str,
    item_id: int | str,
    title: str,
    subtitle: str | None = None,
    due_date: str | None = None,
    severity: str = "warning",
    route: str | None = None,
    event_id: int | None = None,
) -> dict:
    return {
        "category": category,
        "id": item_id,
        "title": title,
        "subtitle": subtitle,
        "due_date": due_date,
        "severity": severity,
        "route": route,
        "event_id": event_id,
    }


def _collect_event_items(company_id: int, limit: int) -> list[dict]:
    events = (
        Event.query.filter_by(company_id=company_id)
        .filter(effectively_overdue_filter())
        .order_by(Event.event_date.asc())
        .limit(limit)
        .all()
    )
    items: list[dict] = []
    for event in events:
        subtitle = get_current_name(event.employment.person) if event.employment else None
        items.append(
            _attention_item(
                category="events",
                item_id=event.id,
                title=event.title,
                subtitle=subtitle,
                due_date=event.event_date.isoformat(),
                severity="danger",
                route=f"/?event={event.id}",
                event_id=event.id,
            )
        )
    return items


def _collect_contract_items(company_id: int, limit: int, today) -> list[dict]:
    employments = Employment.query.filter_by(
        company_id=company_id,
        status=EmploymentStatus.ACTIVE.value,
    ).all()
    candidates: list[tuple[int, dict]] = []
    for employment in employments:
        contract = get_active_contract(employment)
        if not contract:
            continue
        days_left = (contract.end_date - today).days
        if days_left > 120:
            continue
        severity = "danger" if days_left < 0 else "warning"
        related_event = _open_event_for(
            company_id=company_id,
            employment_id=employment.id,
            event_type=EventType.REPORT,
        )
        candidates.append(
            (
                days_left,
                _attention_item(
                    category="contracts",
                    item_id=contract.id,
                    title=get_current_name(employment.person) or "Сотрудник",
                    subtitle=f"Договор до {contract.end_date.isoformat()}",
                    due_date=contract.end_date.isoformat(),
                    severity=severity,
                    route="/contracts",
                    event_id=related_event.id if related_event else None,
                ),
            )
        )
    candidates.sort(key=lambda item: item[0])
    return [item for _, item in candidates[:limit]]


def _collect_passport_items(company_id: int, limit: int, today) -> list[dict]:
    employments = Employment.query.filter_by(
        company_id=company_id,
        status=EmploymentStatus.ACTIVE.value,
    ).all()
    candidates: list[tuple[int, dict]] = []
    for employment in employments:
        passport = get_active_passport(employment.person)
        if not passport:
            candidates.append(
                (
                    99999,
                    _attention_item(
                        category="passports",
                        item_id=employment.person_id,
                        title=get_current_name(employment.person) or "Сотрудник",
                        subtitle="Паспорт не указан",
                        severity="warning",
                        route="/passports",
                    ),
                )
            )
            continue

        days_left = (passport.valid_until - today).days
        status = compute_passport_status(passport.valid_until, today)
        if status not in ("requires_preparation", "expired"):
            continue
        severity = "danger" if status == "expired" else "warning"
        related_event = _open_event_for(
            company_id=company_id,
            employment_id=employment.id,
            event_type=EventType.PASSPORT,
        )
        candidates.append(
            (
                days_left,
                _attention_item(
                    category="passports",
                    item_id=employment.person_id,
                    title=get_current_name(employment.person) or "Сотрудник",
                    subtitle=f"Паспорт до {passport.valid_until.isoformat()}",
                    due_date=passport.valid_until.isoformat(),
                    severity=severity,
                    route="/passports",
                    event_id=related_event.id if related_event else None,
                ),
            )
        )
    candidates.sort(key=lambda item: item[0])
    return [item for _, item in candidates[:limit]]


def _collect_grade_items(company_id: int, limit: int, today) -> list[dict]:
    employments = Employment.query.filter_by(
        company_id=company_id,
        status=EmploymentStatus.ACTIVE.value,
    ).all()
    candidates: list[tuple[int, dict]] = []
    for employment in employments:
        grade = get_current_grade(employment)
        if not grade:
            continue
        eligibility = compute_grade_eligibility(employment, today)
        if not eligibility["next_grade_candidates"] or eligibility["eligible_date"] is None:
            continue
        days_left = eligibility["days_left"]
        if days_left is None or days_left > 30:
            continue
        eligible_date = eligibility["eligible_date"]
        related_event = _open_event_for(
            company_id=company_id,
            employment_id=employment.id,
            event_type=EventType.GRADE,
        )
        candidates.append(
            (
                days_left,
                _attention_item(
                    category="grades",
                    item_id=related_event.id if related_event else employment.id,
                    title=get_current_name(employment.person) or "Сотрудник",
                    subtitle=f"Грейд {grade.grade.name}, eligible {eligible_date.isoformat()}",
                    due_date=eligible_date.isoformat(),
                    severity="warning" if days_left > 0 else "danger",
                    route=f"/?event={related_event.id}" if related_event else "/grades",
                    event_id=related_event.id if related_event else None,
                ),
            )
        )
    candidates.sort(key=lambda item: item[0])
    return [item for _, item in candidates[:limit]]


def _collect_tenure_items(company_id: int, limit: int) -> list[dict]:
    awards = (
        TenureAward.query.filter_by(company_id=company_id, is_received=False)
        .order_by(TenureAward.milestone_date.asc())
        .limit(limit * 3)
        .all()
    )
    items: list[dict] = []
    today = today_moscow()
    for award in awards:
        if not is_tenure_award_auto_eligible(award, today):
            continue
        employment = active_employment(award.person_id, award.company_id)
        if not employment:
            continue
        items.append(
            _attention_item(
                category="tenure",
                item_id=award.id,
                title=get_current_name(employment.person) or "Сотрудник",
                subtitle=f"Поощрение за {award.milestone_years} лет",
                due_date=award.milestone_date.isoformat(),
                severity="warning",
                route="/awards",
            )
        )
        if len(items) >= limit:
            break
    return items


def build_attention_summary(
    company_id: int,
    limit: int = 10,
    categories: list[str] | None = None,
) -> dict:
    selected = categories or list(ALL_CATEGORIES)
    selected_set = {category for category in selected if category in ALL_CATEGORIES}
    if not selected_set:
        selected_set = set(ALL_CATEGORIES)

    today = today_moscow()
    per_category_limit = max(limit, 1)

    collectors = {
        "events": lambda: _collect_event_items(company_id, per_category_limit),
        "contracts": lambda: _collect_contract_items(company_id, per_category_limit, today),
        "passports": lambda: _collect_passport_items(company_id, per_category_limit, today),
        "grades": lambda: _collect_grade_items(company_id, per_category_limit, today),
        "tenure": lambda: _collect_tenure_items(company_id, per_category_limit),
    }

    by_category: dict[str, list[dict]] = {}
    counts: dict[str, int] = {}
    items: list[dict] = []

    for category in ALL_CATEGORIES:
        if category not in selected_set:
            continue
        category_items = collectors[category]()
        by_category[category] = category_items
        counts[category] = len(category_items)
        items.extend(category_items)

    items.sort(key=lambda item: (item.get("due_date") or "9999-12-31", item["title"]))
    if limit > 0:
        items = items[:limit]

    return {
        "total": sum(counts.values()),
        "counts": counts,
        "items": items,
        "by_category": by_category,
    }
