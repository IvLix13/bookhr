"""Rewards API."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import (
    api_response,
    apply_employment_name_search,
    apply_sort,
    get_json,
    join_current_person_name,
    load_schema,
    paginate_query,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.api.schemas import CreateRewardSchema
from app.api.serializers import reward_to_dict
from app.extensions import db
from app.models import Employment, PersonNameHistory, Reward, RoleName
from app.services.rewards import create_reward, update_reward
from app.tenant import get_request_company_id


REWARD_SORT_FIELDS = {
    "reward_type": Reward.reward_type,
    "status": Reward.status,
    "status_changed_date": Reward.status_changed_date,
    "updated_at": Reward.updated_at,
    "delivered_date": Reward.delivered_date,
    "directive_text": Reward.directive_text,
    "notes": Reward.notes,
    "full_name": PersonNameHistory.full_name,
}


def register_routes(bp):
    @bp.get("/rewards")
    @login_required
    def list_rewards():
        company_id = get_request_company_id()
        status = request.args.get("status", type=str)
        employment_id = request.args.get("employment_id", type=int)
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            REWARD_SORT_FIELDS,
            default_field="status_changed_date",
            default_direction="desc",
        )

        query = (
            Reward.query.join(Employment, Reward.employment_id == Employment.id)
            .filter(Employment.company_id == company_id)
        )
        if status:
            query = query.filter(Reward.status == status)
        if employment_id:
            query = query.filter(Reward.employment_id == employment_id)

        query = apply_employment_name_search(query, q)
        if sort == "full_name":
            query = join_current_person_name(query)

        query = apply_sort(query, REWARD_SORT_FIELDS, sort, direction)
        return api_response(paginate_query(query, reward_to_dict, page, per_page))

    @bp.post("/rewards")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_reward_route():
        payload = load_schema(CreateRewardSchema)
        try:
            reward = create_reward(
                employment_id=payload["employment_id"],
                reward_type=payload["reward_type"],
                status=payload.get("status", "not_delivered"),
                directive_text=payload.get("directive_text"),
                status_changed_date=payload.get("status_changed_date"),
                delivered_date=payload.get("delivered_date"),
                notes=payload.get("notes"),
            )
            db.session.commit()
        except ValueError as exc:
            return api_response(message=str(exc), status=400)
        return api_response(reward_to_dict(reward), status=201)

    @bp.patch("/rewards/<int:reward_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_reward_route(reward_id: int):
        reward = db.session.get(Reward, reward_id)
        if not reward:
            return api_response(message="Not found", status=404)
        payload = get_json()
        try:
            reward = update_reward(reward, payload)
            db.session.commit()
        except ValueError as exc:
            return api_response(message=str(exc), status=400)
        return api_response(reward_to_dict(reward))
