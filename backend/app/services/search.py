"""Global search across HR entities."""

from __future__ import annotations

from app.api.serializers import contract_to_dict, employment_to_dict
from app.models import Contract, Employment, EmploymentStatus, Event, Person, PersonNameHistory
from app.services.employees import get_current_name


def _employee_search_query(company_id: int, pattern: str, limit: int):
    return (
        Employment.query.join(Person, Employment.person_id == Person.id)
        .join(
            PersonNameHistory,
            (PersonNameHistory.person_id == Person.id)
            & (PersonNameHistory.valid_to.is_(None)),
        )
        .filter(
            Employment.company_id == company_id,
            PersonNameHistory.full_name.ilike(pattern),
        )
        .order_by(PersonNameHistory.full_name.asc())
        .limit(limit)
        .all()
    )


def search_all(company_id: int, q: str, limit: int = 20) -> dict:
    per_type_limit = max(limit, 1)
    pattern = f"%{q}%"

    employees = _employee_search_query(company_id, pattern, per_type_limit)
    events = (
        Event.query.filter(
            Event.company_id == company_id,
            Event.title.ilike(pattern),
        )
        .order_by(Event.event_date.desc())
        .limit(per_type_limit)
        .all()
    )
    contracts = (
        Contract.query.join(Employment)
        .join(
            PersonNameHistory,
            (PersonNameHistory.person_id == Employment.person_id)
            & (PersonNameHistory.valid_to.is_(None)),
        )
        .filter(
            Employment.company_id == company_id,
            Employment.status == EmploymentStatus.ACTIVE.value,
            Contract.is_active.is_(True),
            PersonNameHistory.full_name.ilike(pattern),
        )
        .order_by(Contract.end_date.asc())
        .limit(per_type_limit)
        .all()
    )

    employee_items = [
        {
            "type": "employee",
            "id": employment.id,
            "title": get_current_name(employment.person) or "",
            "subtitle": employment_to_dict(employment).get("title"),
            "route": "/employees",
        }
        for employment in employees
    ]
    event_items = [
        {
            "type": "event",
            "id": event.id,
            "title": event.title,
            "subtitle": event.event_date.isoformat(),
            "route": "/events",
        }
        for event in events
    ]
    contract_items = [
        {
            "type": "contract",
            "id": contract.id,
            "title": get_current_name(contract.employment.person) or "",
            "subtitle": contract_to_dict(contract)["end_date"],
            "route": "/contracts",
        }
        for contract in contracts
    ]

    groups = {
        "employees": employee_items,
        "events": event_items,
        "contracts": contract_items,
    }
    flat = employee_items + event_items + contract_items
    flat.sort(key=lambda item: item["title"].lower())
    if limit > 0:
        flat = flat[:limit]

    return {
        "query": q,
        "total": len(flat),
        "results": flat,
        "groups": groups,
    }
