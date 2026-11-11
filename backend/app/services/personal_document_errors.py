"""Fetch and publish a snapshot from the external personal-document database."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit

import psycopg
from flask import current_app
from psycopg.rows import dict_row
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.extensions import db
from app.models import PersonalDocumentErrorsSnapshot

SOURCE_QUERY = (
    "SELECT a.id ,a.ldnumber ,a.cardnumber ,a.grade ,a.f ,a.i ,a.o ,a.datebirth ,b.grade_date_check ,"
    "b.post_date_check ,b.contract_date_check ,b.photo_date_check ,b.biography_date_check ,"
    "b.attestation_date_check ,b.passport_date_check FROM public.person a inner join public.person_data b "
    "on a.ldnumber = b.ldnumber where upper(subdivision) = 'Urah' and dispathed = false and "
    "(grade_date_check = false or post_date_check = false or contract_date_check = false or "
    "photo_date_check = false or biography_date_check = false or attestation_date_check = false or "
    "passport_date_check = false)"
)
ERROR_CODES = ("grade", "post", "contract", "photo", "biography", "attestation", "passport")
LOCK_NAMESPACE = 270027


def configured_base_url() -> str | None:
    """Return the external application URL when the integration is configured."""
    config = current_app.config
    if (
        not config["PERSONAL_DOCUMENT_ERRORS_ENABLED"]
        or not config["PERSONAL_DOCUMENT_ERRORS_DSN"].strip()
        or config["PERSONAL_DOCUMENT_ERRORS_COMPANY_ID"] <= 0
        or config["PERSONAL_DOCUMENT_ERRORS_CONNECT_TIMEOUT"] <= 0
        or config["PERSONAL_DOCUMENT_ERRORS_STATEMENT_TIMEOUT_MS"] <= 0
        or config["PERSONAL_DOCUMENT_ERRORS_LOCK_TIMEOUT_MS"] <= 0
    ):
        return None

    url = config["PERSONAL_DOCUMENT_ERRORS_BASE_URL"].strip().rstrip("/")
    if any(character.isspace() or ord(character) < 32 for character in url) or "\\" in url:
        return None
    try:
        parts = urlsplit(url)
        if (
            parts.scheme in {"http", "https"} and parts.hostname
            and parts.username is None and "?" not in url and "#" not in url
            and parts.port != 0
        ):
            return url
    except ValueError:
        pass
    return None


def _read_source() -> list[dict]:
    config = current_app.config
    with psycopg.connect(
        config["PERSONAL_DOCUMENT_ERRORS_DSN"],
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=config["PERSONAL_DOCUMENT_ERRORS_CONNECT_TIMEOUT"],
        # Bound detection of a dropped TCP connection while waiting for the server.
        keepalives=1,
        keepalives_idle=5,
        keepalives_interval=2,
        keepalives_count=3,
        tcp_user_timeout=10000,
        options=(
            f"-c statement_timeout={config['PERSONAL_DOCUMENT_ERRORS_STATEMENT_TIMEOUT_MS']}"
            " -c default_transaction_read_only=on"
        ),
    ) as source:
        with source.cursor() as cursor:
            cursor.execute(SOURCE_QUERY)
            return _normalize_rows(cursor)


def _normalize_rows(rows) -> list[dict]:
    cards = {}
    text_fields = ("cardnumber", "grade", "f", "i", "o")
    for row in rows:
        ldnumber = row["ldnumber"]
        external_id = row["id"]
        if (
            not isinstance(ldnumber, str) or not ldnumber.strip() or ldnumber in {".", ".."}
            or type(external_id) is not int
        ):
            raise ValueError("Invalid personal file identifier")

        if any(row[key] is not None and not isinstance(row[key], str) for key in text_fields):
            raise ValueError("Invalid personal file text fields")
        checks = {code: row[f"{code}_date_check"] for code in ERROR_CODES}
        if any(value is not None and type(value) is not bool for value in checks.values()):
            raise ValueError("Invalid personal file check flags")

        card = cards.get(ldnumber)
        if card is None:
            name_parts = (row[key].strip() for key in ("f", "i", "o") if row[key])
            card = {
                "external_id": external_id,
                "ldnumber": ldnumber,
                "cardnumber": row["cardnumber"],
                "full_name": " ".join(part for part in name_parts if part),
                "grade": row["grade"],
                "errors": set(),
            }
            cards[ldnumber] = card
        elif card["external_id"] != external_id:
            raise ValueError("Conflicting personal file identifiers")

        card["errors"].update(code for code, value in checks.items() if value is False)

    items = [
        {**card, "errors": [code for code in ERROR_CODES if code in card["errors"]]}
        for card in cards.values() if card["errors"]
    ]
    return sorted(items, key=lambda card: (card["full_name"].casefold(), card["ldnumber"]))


def _lock_snapshot(connection, company_id: int) -> bool:
    timeout = current_app.config["PERSONAL_DOCUMENT_ERRORS_LOCK_TIMEOUT_MS"]
    try:
        with connection.begin_nested():
            connection.execute(text("SELECT set_config('lock_timeout', :timeout, true)"), {"timeout": f"{timeout}ms"})
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:namespace, :company_id)"),
                {"namespace": LOCK_NAMESPACE, "company_id": company_id},
            )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) != "55P03":
            raise
        return False
    return True


def refresh_snapshot(company_id: int):
    """Return the result of this entry or the concurrent attempt for the company."""
    table = PersonalDocumentErrorsSnapshot.__table__
    query = select(table).where(table.c.company_id == company_id)

    with db.engine.begin() as connection:
        version = connection.execute(query.with_only_columns(table.c.attempt_version)).scalar_one_or_none()
        acquired = _lock_snapshot(connection, company_id)
        previous = connection.execute(query).mappings().one_or_none()
        # The lock and snapshot use the local database's READ COMMITTED isolation.
        # A change since the first read means another request already published this refresh.
        if previous is not None and previous["attempt_version"] != version:
            return previous, False
        if not acquired:
            return previous, True

        try:
            items = _read_source()
        except (psycopg.Error, ValueError) as error:
            current_app.logger.warning("Personal document errors refresh failed (%s)", type(error).__name__)
            items = None

        completed_at = datetime.now(UTC)
        snapshot = {
            "company_id": company_id,
            "items": previous["items"] if previous is not None else [],
            "last_success_at": previous["last_success_at"] if previous is not None else None,
            "last_attempt_at": completed_at,
            "last_attempt_succeeded": items is not None,
            "attempt_version": (version or 0) + 1,
        }
        if items is not None:
            snapshot.update(items=items, last_success_at=completed_at)
        if previous is None:
            connection.execute(table.insert().values(snapshot))
        else:
            connection.execute(table.update().where(table.c.company_id == company_id).values(snapshot))

    if items is not None:
        current_app.logger.info("Personal document errors refresh published %d cards", len(items))
    return snapshot, False
