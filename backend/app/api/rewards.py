"""Rewards API."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import api_response, get_json, require_roles
from app.api.serializers import reward_to_dict
from app.extensions import db
from app.models import Reward, RoleName
from app.services.rewards import create_reward, list_rewards_for_company, update_reward


def register_routes(bp):
    @bp.get("/rewards")
    @login_required
    def list_rewards():
        company_id = request.args.get("company_id", 1, type=int)
        status = request.args.get("status", type=str)
        employment_id = request.args.get("employment_id", type=int)
        rewards = list_rewards_for_company(company_id, status=status, employment_id=employment_id)
        return api_response([reward_to_dict(reward) for reward in rewards])

    @bp.post("/rewards")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_reward_route():
        payload = get_json()
        try:
            reward = create_reward(
                employment_id=payload["employment_id"],
                reward_type=payload["reward_type"],
                status=payload.get("status", "not_delivered"),
                directive_text=payload.get("directive_text"),
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
