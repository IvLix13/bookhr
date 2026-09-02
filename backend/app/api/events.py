"""Events API."""

from __future__ import annotations

from flask import request
from flask_login import login_required

from app.api.helpers import (
    api_response,
    apply_sort,
    apply_text_search,
    load_schema,
    nearest_event_date_sort_key,
    paginate_query,
    paginate_sequence,
    parse_pagination_args,
    parse_search_q,
    parse_sort_args,
    require_roles,
)
from app.api.schemas import CreateEventSchema, EventActionSchema, UpdateEventSchema, parse_query_date
from app.api.serializers import event_to_dict
from app.extensions import db
from app.models import Event, EventStatus, Employment, PersonNameHistory, RoleName, User
from app.services.event_completion import apply_completion_effects
from app.services.events import (
    EventMutationError,
    InvalidEventTransition,
    apply_status_filter,
    create_manual_event,
    delete_manual_event,
    planned_nearest_event_sort_key,
    refresh_events_after_mutation,
    refresh_overdue_events,
    transition_event_status,
    update_manual_event,
)
from app.tenant import get_request_company_id


EVENT_NEAREST_SORT = "nearest_date"
EVENT_PLANNED_NEAREST_SORT = "planned_nearest"

EVENT_SORT_FIELDS = {
    EVENT_PLANNED_NEAREST_SORT: Event.event_date,
    EVENT_NEAREST_SORT: Event.event_date,
    "event_date": Event.event_date,
    "title": Event.title,
    "status": Event.status,
    "event_type": Event.event_type,
    "source": Event.source,
    "employee_name": PersonNameHistory.full_name,
    "created_by": User.full_name,
}


def _apply_event_list_sort_joins(query, sort: str):
    if sort == "employee_name":
        return (
            query.outerjoin(Employment, Event.employment_id == Employment.id)
            .outerjoin(
                PersonNameHistory,
                (PersonNameHistory.person_id == Employment.person_id)
                & (PersonNameHistory.valid_to.is_(None)),
            )
        )
    if sort == "created_by":
        return query.outerjoin(User, Event.created_by_id == User.id)
    return query


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
            default_field=EVENT_PLANNED_NEAREST_SORT,
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

        if sort in (EVENT_NEAREST_SORT, EVENT_PLANNED_NEAREST_SORT):
            events = query.all()
            if sort == EVENT_PLANNED_NEAREST_SORT:
                events.sort(key=planned_nearest_event_sort_key)
            else:
                events.sort(
                    key=lambda event: nearest_event_date_sort_key(
                        event.event_date,
                        tie_breaker=event.id,
                    )
                )
            return api_response(
                paginate_sequence([event_to_dict(event) for event in events], page, per_page)
            )

        query = _apply_event_list_sort_joins(query, sort)
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

        query = Event.query.filter_by(company_id=company_id)
        # Only future/today planned — overdue belong in attention, not upcoming.
        query = apply_status_filter(query, EventStatus.PLANNED.value)
        events = query.order_by(Event.event_date.asc()).limit(limit).all()
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
        refresh_events_after_mutation(
            company_id=event.company_id,
            employment=event.employment,
        )
        db.session.commit()
        return api_response(event_to_dict(event), status=201)

    @bp.patch("/events/<int:event_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def update_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event or event.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)
        payload = load_schema(UpdateEventSchema)
        employment_before = event.employment
        try:
            event = update_manual_event(event, payload)
            refresh_events_after_mutation(
                company_id=event.company_id,
                employment=event.employment or employment_before,
            )
        except EventMutationError as exc:
            return api_response(message=str(exc), status=409)
        db.session.commit()
        return api_response(event_to_dict(event))

    @bp.delete("/events/<int:event_id>")
    @require_roles(RoleName.ADMIN, RoleName.HR)
    def delete_event(event_id: int):
        event = db.session.get(Event, event_id)
        if not event or event.company_id != get_request_company_id():
            return api_response(message="Not found", status=404)
        company_id = event.company_id
        employment = event.employment
        try:
            delete_manual_event(event)
        except EventMutationError as exc:
            return api_response(message=str(exc), status=409)
        refresh_events_after_mutation(company_id=company_id, employment=employment)
        db.session.commit()
        return api_response(message="Deleted")

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
            apply_completion_effects(
                event,
                term_years=payload.get("extension_term_years"),
                new_end_date=payload.get("new_end_date"),
                target_grade_id=payload.get("target_grade_id"),
                new_passport_valid_until=payload.get("new_passport_valid_until"),
            )
        except InvalidEventTransition as exc:
            return api_response(message=str(exc), status=409)
        except ValueError as exc:
            db.session.rollback()
            return api_response(message=str(exc), status=400)
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
        refresh_events_after_mutation(
            company_id=event.company_id,
            employment=event.employment,
        )
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
        refresh_events_after_mutation(
            company_id=event.company_id,
            employment=event.employment,
        )
        db.session.commit()
        return api_response(event_to_dict(event))
