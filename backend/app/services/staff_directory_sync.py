"""Apply trusted directory fields to existing people, preserving all local grades."""
from __future__ import annotations

import hashlib
import math
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Employment, EmploymentStatus, Person, PersonNameHistory, PositionHistory, StaffDirectoryState
from app.services.audit import log_audit
from app.services.employees import get_current_name, get_current_position, update_position
from app.services.staff_directory_client import StaffDirectoryClient, StaffDirectoryError
from app.utils.dates import today_moscow

LOCK_ID = 741926304


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def normalize_name(value):
    return " ".join((value or "").split()).casefold().replace("ё", "е")


def split_name(value):
    parts = (value or "").split()
    if len(parts) not in (2, 3) or any(
        not re.fullmatch(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*", part, re.UNICODE) or len(part) < 2
        for part in parts
    ):
        return None
    return parts + [None] * (3 - len(parts))


@contextmanager
def sync_lock():
    """One lock for all companies, manual runs and dry-runs using this database."""
    if db.engine.dialect.name == "postgresql":
        with db.engine.connect() as connection:
            acquired = connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}).scalar()
            connection.commit()
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                    connection.commit()
        return
    # Local SQLite development; the kernel releases the lock after a crash.
    digest = hashlib.sha256(str(db.engine.url).encode()).hexdigest()[:24]
    path = Path(tempfile.gettempdir()) / ("bookhr-staff-sync-" + digest + ".lock")
    with path.open("a+b") as handle:
        acquired = False
        try:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
            yield acquired
        finally:
            if acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _snapshot(person_id, *, lock=False):
    query = Person.query.filter_by(id=person_id)
    if lock:
        query = query.with_for_update()
    person = query.first()
    if person is None:
        return None
    names = PersonNameHistory.query.filter_by(person_id=person.id, valid_to=None).order_by(PersonNameHistory.id)
    active = Employment.query.filter_by(person_id=person.id, status=EmploymentStatus.ACTIVE.value).order_by(Employment.id)
    if lock:
        names, active = names.with_for_update(), active.with_for_update()
    names, active = names.all(), active.all()
    positions = PositionHistory.query.filter(
        PositionHistory.employment_id.in_([e.id for e in active]), PositionHistory.valid_to.is_(None)
    ).order_by(PositionHistory.id)
    if lock:
        positions = positions.with_for_update()
    return {
        "person": (person.cardnumber, person.fio_short, person.updated_at, person.staff_directory_checked_at),
        "names": [(n.id, n.full_name) for n in names],
        "active": [(e.id, e.company_id, e.updated_at, e.formal_department_short_name, e.formal_department_name) for e in active],
        "positions": [(p.id, p.employment_id, p.title, p.short_title, p.position_grade_id) for p in positions],
    }


def _matching_record(people, cardnumber):
    if not people:
        return None, "not_found"
    if cardnumber:
        matches = [p for p in people if p.get("cardnumber") == cardnumber]
        if len(matches) != 1:
            return None, "cardnumber_mismatch" if not matches else "ambiguous"
        return matches[0], None
    if len(people) != 1:
        return None, "ambiguous"
    if not people[0].get("cardnumber"):
        return None, "missing_cardnumber"
    return people[0], None


def _apply(person, record, active, *, dry_run):
    """Return an explicit change set, including partial updates for multiple jobs."""
    before, after = {}, {}
    for field in ("cardnumber", "fio_short"):
        if field in record and getattr(person, field) != record[field]:
            before[field], after[field] = getattr(person, field), record[field]
            if not dry_run:
                setattr(person, field, record[field])
    if len(active) == 1:
        employment = active[0]
        position = get_current_position(employment)
        old_title = position.title if position else None
        old_short = position.short_title if position else None
        title = (record["position_name"] or "Не указана") if "position_name" in record else old_title
        short = record.get("position_short_name", old_short)
        # Omitted position keys must not manufacture a position history entry.
        if ("position_name" in record or "position_short_name" in record) and (
            title != old_title or short != old_short
        ):
            before.update(position_name=old_title, position_short_name=old_short)
            after.update(position_name=title or "Не указана", position_short_name=short)
            if not dry_run:
                update_position(
                    employment, title or "Не указана",
                    position.position_grade_id if position else None,
                    today_moscow(), short_title=short,
                )
        for field in ("formal_department_short_name", "formal_department_name"):
            if field in record and getattr(employment, field) != record[field]:
                before[field], after[field] = getattr(employment, field), record[field]
                if not dry_run:
                    setattr(employment, field, record[field])
    if after and not dry_run:
        log_audit("sync", "staff_directory", person.id, before, after)
    if len(active) != 1:
        outcome = "partial" if after else "ambiguous_employment"
    else:
        outcome = "updated" if after else "unchanged"
    return outcome, before, after


def sync_staff_directory(*, company_id=None, person_id=None, dry_run=False, client_factory=None, report=None):
    """Run bounded work. CLI owns this session; commits are per person."""
    config = current_app.config
    stats = {"examined": 0, "requests": 0, "errors": 0, "dry_run": dry_run}
    emit = report or (lambda detail: None)
    if not config.get("STAFF_DIRECTORY_ENABLED"):
        stats["disabled"] = True
        return stats
    batch_size = int(config.get("STAFF_DIRECTORY_BATCH_SIZE", 100))
    min_hours = float(config.get("STAFF_DIRECTORY_MIN_SYNC_HOURS", 6))
    if not 1 <= batch_size <= 1000 or not math.isfinite(min_hours) or min_hours < 1:
        raise StaffDirectoryError("invalid_configuration", fatal=True)
    with sync_lock() as acquired:
        if not acquired:
            stats["already_running"] = True
            return stats
        state = db.session.get(StaffDirectoryState, 1)
        if state and aware(state.blocked_until) and aware(state.blocked_until) > utcnow():
            stats.update(cooldown=True, blocked_until=aware(state.blocked_until).isoformat())
            db.session.rollback()
            return stats
        cutoff = utcnow() - timedelta(hours=min_hours)
        active_filter = [Employment.status == EmploymentStatus.ACTIVE.value]
        if company_id is not None:
            active_filter.append(Employment.company_id == company_id)
        query = Person.query.filter(
            Person.employments.any(and_(*active_filter)),
            or_(Person.staff_directory_checked_at.is_(None), Person.staff_directory_checked_at <= cutoff),
        )
        if person_id is not None:
            query = query.filter(Person.id == person_id)
        ids = [row[0] for row in query.with_entities(Person.id).order_by(
            Person.staff_directory_checked_at.asc().nullsfirst(), Person.id
        ).yield_per(batch_size)]
        # Group duplicate current full names before any external identity is assigned.
        all_names = {}
        for pid, name in db.session.query(PersonNameHistory.person_id, PersonNameHistory.full_name).filter_by(valid_to=None):
            all_names.setdefault(normalize_name(name), set()).add(pid)
        db.session.rollback()
        client = (client_factory or StaffDirectoryClient)(config)
        consecutive_errors = 0
        try:
            for pid in ids:
                snapshot = _snapshot(pid)
                if not snapshot or not snapshot["active"]:
                    db.session.rollback()
                    continue
                person = db.session.get(Person, pid)
                name = get_current_name(person)
                parts = split_name(name)
                local_reason = None
                if not parts or len(snapshot["names"]) != 1:
                    local_reason = "invalid_local_name"
                elif not person.cardnumber and len(all_names.get(normalize_name(name), ())) > 1:
                    local_reason = "ambiguous_local_name"
                cardnumber = person.cardnumber
                db.session.rollback()  # Never hold a transaction across HTTP or rate-limit sleeps.
                try:
                    people = [] if local_reason else client.find_staff_by_fio(*parts)
                    record, reason = (None, local_reason) if local_reason else _matching_record(people, cardnumber)
                    consecutive_errors = 0
                    # Discard expired identity-map state and lock only while applying results.
                    db.session.expire_all()
                    current = _snapshot(pid, lock=True)
                    if current != snapshot:
                        db.session.rollback()
                        emit({"person_id": pid, "status": "stale"})
                        stats["stale"] = stats.get("stale", 0) + 1
                        continue
                    person = db.session.get(Person, pid)
                    before, after = {}, {}
                    if record:
                        taken = Person.query.filter(Person.cardnumber == record["cardnumber"], Person.id != pid).first()
                        if taken:
                            reason = "cardnumber_conflict"
                        else:
                            active = Employment.query.filter_by(person_id=pid, status=EmploymentStatus.ACTIVE.value).all()
                            reason, before, after = _apply(person, record, active, dry_run=dry_run)
                    if dry_run:
                        db.session.rollback()
                    else:
                        person.staff_directory_checked_at = utcnow()
                        db.session.commit()
                    stats["examined"] += 1
                    stats[reason] = stats.get(reason, 0) + 1
                    emit({"person_id": pid, "status": reason, "before": before, "after": after})
                except StaffDirectoryError as exc:
                    db.session.rollback()
                    if exc.code == "run_budget_exhausted":
                        stats["budget_exhausted"] = True
                        break
                    stats["errors"] += 1
                    emit({"person_id": pid, "status": exc.code})
                    consecutive_errors += 1
                    if exc.fatal or consecutive_errors >= 3:
                        # Persist upstream Retry-After for subsequent manual/timer runs.
                        cooldown = max(exc.cooldown, 300 if consecutive_errors >= 3 else 0)
                        if cooldown and not dry_run:
                            state = db.session.get(StaffDirectoryState, 1)
                            if state is None:
                                state = StaffDirectoryState(id=1)
                                db.session.add(state)
                            state.blocked_until = utcnow() + timedelta(seconds=cooldown)
                            db.session.commit()
                        stats["stopped"] = exc.code
                        break
                except SQLAlchemyError:
                    db.session.rollback()
                    stats["errors"] += 1
                    emit({"person_id": pid, "status": "database_error"})
        finally:
            stats["requests"] = client.requests_made
            client.close()
            db.session.rollback()
    return stats
