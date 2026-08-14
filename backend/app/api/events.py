"""Events API."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import (
    api_response,
    apply_sort,
    apply_text_search,
    load_schema,
    paginate_query,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.api.schemas import CreateEventSchema, EventActionSchema, parse_query_date
from app.api.serializers import event_to_dict
from app.extensions import db
from app.models import Event, EventStatus, RoleName
from app.services.event_completion import apply_completion_effects
from app.services.events import (
    InvalidEventTransition,
    apply_status_filter,
    create_manual_event,
    refresh_overdue_events,
    transition_event_status,
)
from app.tenant import get_request_company_id


EVENT_SORT_FIELDS = {
    "event_date": Event.event_date,
    "title": Event.title,
    "status": Event.status,
    "event_type": Event.event_type,
}


def register_routes(bp):
    @bp.get("/events")
    @login_required
    def list_events():
        company_id = get_request_company_id()
        date_from = parse_query_date(request.args.get("from"), field_name="from")
        date_to = parse_query_date(request.args.get("to"), field_name="to")
        status = request.args.get("status")
        event_type = request.args.get("type")
        page, per_page = parse_pagination_args()
        q = parse_search_q()
        sort, direction = parse_sort_args(
            EVENT_SORT_FIELDS,
            default_field="event_date",
            default_direction="asc",
        )

        query = Event.query.filter_by(company_id=company_id)
        if date_from:
            query = query.filter(Event.event_date >= date_from)
        if date_to:
            query = query.filter(Event.event_date <= date_to)
        query = apply_status_filter(query, status)
        if event_type:
            query = query.filter_by(event_type=event_type)

        query = apply_text_search(query, Event.title, q)
        query = apply_sort(query, EVENT_SORT_FIELDS, sort, direction)

        return api_response(paginate_query(query, event_to_dict, page, per_page))

    @bp.get("/events/<int:event_id>")
    @login_required
    def get_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event or event.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)
        return api_response(event_to_dict(event))

    @bp.get("/events/upcoming")
    @login_required
    def upcoming_events():
        company_id = get_request_company_id()
        limit = request.args.get("limit", 10, type=int)

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
        payload = load_schema(CreateEventSchema)
        event = create_manual_event(
            company_id=get_request_company_id(),
            title=payload["title"],
            event_type=payload["event_type"],
            event_date=payload["event_date"],
            description=payload.get("description"),
            employment_id=payload.get("employment_id"),
        )
        db.session.commit()
        return api_response(event_to_dict(event), status=201)

    @bp.post("/events/<int:event_id>/complete")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def complete_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event or event.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)
        payload = load_schema(EventActionSchema)
        try:
            transition_event_status(
                event,
                EventStatus.COMPLETED,
                payload.get("comment"),
            )
        except InvalidEventTransition as exc:
            return api_response(message=str(exc), status=409)
        apply_completion_effects(event)
        refresh_overdue_events(event.company_id)
        db.session.commit()
        return api_response(event_to_dict(event))

    @bp.post("/events/<int:event_id>/cancel")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def cancel_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event or event.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)
        payload = load_schema(EventActionSchema)
        try:
            transition_event_status(
                event,
                EventStatus.CANCELLED,
                payload.get("comment"),
            )
        except InvalidEventTransition as exc:
            return api_response(message=str(exc), status=409)
        db.session.commit()
        return api_response(event_to_dict(event))

    @bp.post("/events/<int:event_id>/reopen")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def reopen_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event or event.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)
        try:
            transition_event_status(
                event,
                EventStatus.PLANNED,
                "Reopened",
                force=True,
            )
        except InvalidEventTransition as exc:
            return api_response(message=str(exc), status=409)
        db.session.commit()
        return api_response(event_to_dict(event))
