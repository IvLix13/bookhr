"""Excel import service."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    ImportJob,
    ImportRow,
    ImportStatus,
    Passport,
    Person,
)
from app.services.employees import (
    create_person_with_employment,
    get_current_name,
    get_current_position,
)
from app.services.tenure import ensure_tenure_awards
from app.utils.dates import normalize_full_name

COLUMN_MAP = {
    "uuid": "uuid",
    "фio": "full_name",
    "фио": "full_name",
    "full_name": "full_name",
    "должность": "title",
    "title": "title",
    "грейд по должности": "position_grade",
    "position_grade": "position_grade",
    "фактический грейд": "actual_grade",
    "actual_grade": "actual_grade",
    "вуз": "has_university",
    "has_university": "has_university",
    "окончание договора": "contract_end",
    "contract_end": "contract_end",
    "дата получения текущего грейда": "grade_date",
    "grade_date": "grade_date",
    "начало работы": "hire_date",
    "hire_date": "hire_date",
    "срок окончания паспорта": "passport_until",
    "passport_until": "passport_until",
    "№ п/п": "row_num",
    "row_num": "row_num",
}


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace("  ", " ")


def _parse_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"да", "yes", "1", "true", "+", "есть"}


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_grade_id(name: str | None) -> int | None:
    if not name:
        return None
    from app.models import GradeCatalog

    grade = GradeCatalog.query.filter(
        db.func.lower(GradeCatalog.name) == name.strip().lower()
    ).first()
    return grade.id if grade else None


def parse_workbook(path: Path) -> list[dict[str, Any]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [_normalize_header(str(h or "")) for h in rows[0]]
    mapped_headers = [COLUMN_MAP.get(h, h) for h in headers]
    parsed: list[dict[str, Any]] = []

    for idx, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue
        data = {mapped_headers[i]: row[i] for i in range(len(mapped_headers)) if i < len(row)}
        data["_row_number"] = idx
        parsed.append(data)
    return parsed


def validate_row(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not data.get("full_name"):
        errors.append("Не указано ФИО")

    if not _parse_date(data.get("hire_date")):
        errors.append("Не указана или некорректна дата начала работы")

    person_uuid = data.get("uuid")
    if person_uuid:
        try:
            uuid.UUID(str(person_uuid))
        except ValueError:
            errors.append("Некорректный UUID")
    else:
        warnings.append("UUID отсутствует — потребуется сопоставление")

    return errors, warnings


def find_person_candidates(full_name: str) -> list[Person]:
    normalized = normalize_full_name(str(full_name))
    matches: list[Person] = []
    for person in Person.query.all():
        current_name = get_current_name(person)
        if current_name and normalize_full_name(current_name) == normalized:
            matches.append(person)
    return matches


def dry_run_import(job: ImportJob, rows: list[dict[str, Any]]) -> None:
    summary = {"create": 0, "update": 0, "ambiguous": 0, "error": 0}
    for data in rows:
        row_number = data.get("_row_number", 0)
        errors, warnings = validate_row(data)
        action = None
        person_uuid = None

        if errors:
            action = "error"
            summary["error"] += 1
        elif data.get("uuid"):
            person = Person.query.filter_by(uuid=uuid.UUID(str(data["uuid"]))).first()
            if person:
                action = "update"
                person_uuid = person.uuid
                summary["update"] += 1
            else:
                action = "create"
                summary["create"] += 1
        else:
            candidates = find_person_candidates(str(data.get("full_name", "")))
            if len(candidates) == 1:
                action = "update"
                person_uuid = candidates[0].uuid
                summary["update"] += 1
            elif len(candidates) > 1:
                action = "ambiguous"
                summary["ambiguous"] += 1
                warnings.append("Найдено несколько кандидатов")
            else:
                action = "create"
                summary["create"] += 1

        db.session.add(
            ImportRow(
                import_job_id=job.id,
                row_number=row_number,
                raw_data={k: str(v) if v is not None else None for k, v in data.items()},
                action=action,
                person_uuid=person_uuid,
                errors=errors or None,
                warnings=warnings or None,
            )
        )

    job.status = ImportStatus.VALIDATED.value
    job.summary = summary


def confirm_import(job: ImportJob, row_actions: dict[int, str | None] | None = None) -> None:
    row_actions = row_actions or {}
    for row in job.rows:
        if row.action == "error":
            continue

        action = row_actions.get(row.id, row.action)
        data = row.raw_data
        hire_date = _parse_date(data.get("hire_date"))
        if not hire_date:
            continue

        person: Person | None = None
        employment: Employment | None = None

        if action == "update" and row.person_uuid:
            person = Person.query.filter_by(uuid=row.person_uuid).first()
            if person:
                employment = (
                    Employment.query.filter_by(
                        person_id=person.id,
                        company_id=job.company_id,
                    )
                    .order_by(Employment.hire_date.desc())
                    .first()
                )

        if action == "create" or person is None:
            person, employment = create_person_with_employment(
                company_id=job.company_id,
                full_name=str(data.get("full_name", "")),
                hire_date=hire_date,
                title=str(data.get("title") or "Не указана"),
                position_grade_id=_resolve_grade_id(data.get("position_grade")),
                has_university=_parse_bool(data.get("has_university")),
            )
            row.person_uuid = person.uuid

        if employment is None and person:
            employment = (
                Employment.query.filter_by(person_id=person.id, company_id=job.company_id)
                .order_by(Employment.hire_date.desc())
                .first()
            )

        if employment is None:
            continue

        person.has_university = _parse_bool(data.get("has_university"))

        contract_end = _parse_date(data.get("contract_end"))
        if contract_end:
            existing_contract = Contract.query.filter_by(
                employment_id=employment.id,
                end_date=contract_end,
            ).first()
            if not existing_contract:
                db.session.add(
                    Contract(
                        employment_id=employment.id,
                        start_date=hire_date,
                        end_date=contract_end,
                        is_active=True,
                    )
                )

        grade_date = _parse_date(data.get("grade_date"))
        grade_id = _resolve_grade_id(data.get("actual_grade"))
        if grade_id and grade_date:
            db.session.add(
                EmployeeGradeHistory(
                    employment_id=employment.id,
                    grade_id=grade_id,
                    assigned_date=grade_date,
                )
            )

        passport_until = _parse_date(data.get("passport_until"))
        if passport_until:
            db.session.add(
                Passport(
                    person_id=person.id,
                    valid_until=passport_until,
                    is_active=True,
                )
            )

        ensure_tenure_awards(employment.id, employment.hire_date)

    job.status = ImportStatus.CONFIRMED.value
    db.session.commit()


def export_template_with_uuids(company_id: int, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    headers = [
        "№ п/п",
        "UUID",
        "ФИО",
        "Должность",
        "Грейд по должности",
        "Фактический грейд",
        "ВУЗ",
        "Окончание договора",
        "Дата получения текущего грейда",
        "Начало работы",
        "Срок окончания паспорта",
    ]
    ws.append(headers)

    employments = Employment.query.filter_by(company_id=company_id).all()
    for idx, employment in enumerate(employments, start=1):
        person = employment.person
        position = get_current_position(employment)
        from app.services.employees import get_active_contract, get_active_passport, get_current_grade

        contract = get_active_contract(employment)
        grade = get_current_grade(employment)
        passport = get_active_passport(person)

        ws.append(
            [
                idx,
                str(person.uuid),
                get_current_name(person),
                position.title if position else "",
                position.position_grade.name if position and position.position_grade else "",
                grade.grade.name if grade else "",
                "Да" if person.has_university else "Нет",
                contract.end_date.isoformat() if contract else "",
                grade.assigned_date.isoformat() if grade else "",
                employment.hire_date.isoformat(),
                passport.valid_until.isoformat() if passport else "",
            ]
        )

    wb.save(path)
