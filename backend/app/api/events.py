"""Events API."""

from __future__ import annotations

from datetime import date

from flask import request
from flask_login import login_required

from app.api.helpers import api_response, get_json, paginate_query, require_roles
from app.api.serializers import event_to_dict
from app.extensions import db
from app.models import Event, EventStatus, EventType, RoleName
from app.services.events import create_manual_event, refresh_overdue_events, transition_event_status


def register_routes(bp):
    @bp.get("/events")
    @login_required
    def list_events():
        company_id = request.args.get("company_id", 1, type=int)
        date_from = request.args.get("from")
        date_to = request.args.get("to")
        status = request.args.get("status")
        event_type = request.args.get("type")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        query = Event.query.filter_by(company_id=company_id)
        if date_from:
            query = query.filter(Event.event_date >= date.fromisoformat(date_from))
        if date_to:
            query = query.filter(Event.event_date <= date.fromisoformat(date_to))
        if status:
            query = query.filter_by(status=status)
        if event_type:
            query = query.filter_by(event_type=event_type)
        query = query.order_by(Event.event_date.asc())

        return api_response(paginate_query(query, event_to_dict, page, per_page))

    @bp.get("/events/upcoming")
    @login_required
    def upcoming_events():
        company_id = request.args.get("company_id", 1, type=int)
        limit = request.args.get("limit", 10, type=int)
        refresh_overdue_events(company_id)

        events = (
            Event.query.filter_by(company_id=company_id)
            .filter(
                Event.status.in_([EventStatus.PLANNED.value, EventStatus.OVERDUE.value])
            )
            .order_by(Event.event_date.asc())
            .limit(limit)
            .all()
        )
        return api_response([event_to_dict(e) for e in events])

    @bp.post("/events")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def create_event():
        payload = get_json()
        event = create_manual_event(
            company_id=payload.get("company_id", 1),
            title=payload["title"],
            event_type=EventType(payload.get("event_type", EventType.MANUAL.value)),
            event_date=date.fromisoformat(payload["event_date"]),
            description=payload.get("description"),
            employment_id=payload.get("employment_id"),
        )
        db.session.commit()
        return api_response(event_to_dict(event), status=201)

    @bp.post("/events/<int:event_id>/complete")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def complete_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event:
            return api_response(message="Not found", status=404)
        payload = get_json()
        transition_event_status(
            event,
            EventStatus.COMPLETED,
            payload.get("comment"),
        )
        db.session.commit()
        return api_response(event_to_dict(event))

    @bp.post("/events/<int:event_id>/cancel")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def cancel_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event:
            return api_response(message="Not found", status=404)
        payload = get_json()
        transition_event_status(
            event,
            EventStatus.CANCELLED,
            payload.get("comment"),
        )
        db.session.commit()
        return api_response(event_to_dict(event))

    @bp.post("/events/<int:event_id>/reopen")
    @require_roles(RoleName.ADMIN)
    def reopen_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event:
            return api_response(message="Not found", status=404)
        transition_event_status(event, EventStatus.PLANNED, "Reopened by admin")
        db.session.commit()
        return api_response(event_to_dict(event))
