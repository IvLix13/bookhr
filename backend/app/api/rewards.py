"""Rewards (tenure awards) API."""

from __future__ import annotations

from datetime import date

from flask import request
from flask_login import login_required

from app.api.helpers import (
    api_response,
    apply_employment_name_search,
    apply_sort,
    get_json,
    paginate_query,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.api.serializers import reward_to_dict
from app.extensions import db
from app.models import Employment, EmploymentStatus, PersonNameHistory, RoleName, TenureAward


REWARD_SORT_FIELDS = {
    "milestone_date": TenureAward.milestone_date,
    "milestone_years": TenureAward.milestone_years,
    "is_received": TenureAward.is_received,
    "full_name": PersonNameHistory.full_name,
}


def register_routes(bp):
    @bp.get("/rewards")
    @login_required
    def list_rewards():
        company_id = request.args.get("company_id", 1, type=int)
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            REWARD_SORT_FIELDS,
            default_field="milestone_date",
            default_direction="desc",
        )

        query = (
            TenureAward.query.join(Employment)
            .filter(
                Employment.company_id == company_id,
                Employment.status == EmploymentStatus.ACTIVE.value,
            )
        )
        query = apply_employment_name_search(query, q)

        if sort == "full_name" and not q:
            from app.models import Person

            query = query.join(Person, Employment.person_id == Person.id).join(
                PersonNameHistory,
                (PersonNameHistory.person_id == Person.id)
                & (PersonNameHistory.valid_to.is_(None)),
            ).distinct()

        query = apply_sort(query, REWARD_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, reward_to_dict, page, per_page))

    @bp.patch("/rewards/<int:award_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_reward(award_id: int):
        award = db.session.get(TenureAward, award_id)
        if not award:
            return api_response(message="Not found", status=404)

        payload = get_json()
        award.is_received = payload.get("is_received", award.is_received)
        if payload.get("received_date"):
            award.received_date = date.fromisoformat(payload["received_date"])
        db.session.commit()
        return api_response(reward_to_dict(award))
