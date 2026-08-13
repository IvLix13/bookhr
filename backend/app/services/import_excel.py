"""Excel import service."""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from app.extensions import db
from app.models import (
    Contract,
    EmployeeGradeHistory,
    Employment,
    GradeCatalog,
    ImportJob,
    ImportRow,
    ImportStatus,
    Passport,
    Person,
)
from app.services.employees import (
    create_person_with_employment,
    get_active_contract,
    get_active_passport,
    get_current_grade,
    get_current_name,
    get_current_position,
)
from app.services.events import refresh_overdue_events
from app.services.rule_engine import run_rule_engine
from app.services.tenure import auto_mark_reached_awards, ensure_tenure_awards
from app.utils.dates import format_display_date_ru, normalize_full_name, parse_flexible_date

COLUMN_MAP = {
    "фио": "full_name",
    "full_name": "full_name",
    "должность": "title",
    "title": "title",
    "грейдов по должности": "position_grade",
    "грейд по должности": "position_grade",
    "position_grade": "position_grade",
    "фактический грейдов": "actual_grade",
    "фактический грейд": "actual_grade",
    "actual_grade": "actual_grade",
    "вуз": "has_university",
    "has_university": "has_university",
    "окончание договора": "contract_end",
    "contract_end": "contract_end",
    "дата получения текущего грейда": "grade_date",
    "дата получения текущего грейды": "grade_date",
    "grade_date": "grade_date",
    "начало работы": "hire_date",
    "hire_date": "hire_date",
    "срок окончания паспорта": "passport_until",
    "passport_until": "passport_until",
    "№ п/п": "row_num",
    "row_num": "row_num",
}

DATE_FIELDS = {"hire_date", "contract_end", "grade_date", "passport_until"}
GRADE_FIELDS = ("position_grade", "actual_grade")
UNKNOWN_GRADE_WARNING_PREFIX = "Грейд «"
UNKNOWN_GRADE_WARNING_SUFFIX = "» не найден в справочнике"


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _parse_bool(value: Any) -> bool:
    parsed = _parse_bool_optional(value)
    return bool(parsed)


def _parse_bool_optional(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"да", "yes", "1", "true", "+", "есть"}:
        return True
    if text in {"нет", "no", "0", "false", "-"}:
        return False
    return None


def _parse_date(value: Any) -> date | None:
    return parse_flexible_date(value)


def _normalize_grade_name(name: str | None) -> str:
    if name is None:
        return ""
    return str(name).strip().lower()


def _resolve_grade_id(name: str | None) -> int | None:
    needle = _normalize_grade_name(name)
    if not needle:
        return None
    for grade in GradeCatalog.query.all():
        if grade.name.strip().lower() == needle:
            return grade.id
    return None


def _catalog_name_set() -> set[str]:
    names: set[str] = set()
    for grade in GradeCatalog.query.all():
        normalized = _normalize_grade_name(grade.name)
        if normalized:
            names.add(normalized)
    return names


def _row_grade_values(data: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in GRADE_FIELDS:
        raw = data.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        needle = _normalize_grade_name(text)
        if not needle or needle in seen:
            continue
        seen.add(needle)
        values.append(text)
    return values


def _unknown_grade_warning(name: str) -> str:
    return f"{UNKNOWN_GRADE_WARNING_PREFIX}{name}{UNKNOWN_GRADE_WARNING_SUFFIX}"


def _is_unknown_grade_warning(message: str) -> bool:
    return message.startswith(UNKNOWN_GRADE_WARNING_PREFIX) and message.endswith(
        UNKNOWN_GRADE_WARNING_SUFFIX
    )


def _serialize_raw_data(data: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if key in DATE_FIELDS:
            parsed = _parse_date(value)
            serialized[key] = parsed.isoformat() if parsed else None
            continue
        if key == "has_university":
            optional = _parse_bool_optional(value)
            if optional is None:
                serialized[key] = None
            else:
                serialized[key] = "Да" if optional else "Нет"
            continue
        serialized[key] = None if value is None else str(value)
    return serialized


def candidate_payload(person: Person) -> dict[str, str | None]:
    employment = (
        Employment.query.filter_by(person_id=person.id)
        .order_by(Employment.hire_date.desc())
        .first()
    )
    title = None
    if employment:
        position = get_current_position(employment)
        title = position.title if position else None
    return {
        "uuid": str(person.uuid),
        "full_name": get_current_name(person),
        "title": title,
    }


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
        data.pop("uuid", None)
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
        candidates: list[dict[str, str | None]] | None = None

        if errors:
            action = "error"
            summary["error"] += 1
        else:
            matches = find_person_candidates(str(data.get("full_name", "")))
            if len(matches) == 1:
                action = "update"
                person_uuid = matches[0].uuid
                summary["update"] += 1
            elif len(matches) > 1:
                action = "ambiguous"
                candidates = [candidate_payload(person) for person in matches]
                summary["ambiguous"] += 1
                warnings.append("Найдено несколько кандидатов — выберите действие")
            else:
                action = "create"
                summary["create"] += 1

        db.session.add(
            ImportRow(
                import_job_id=job.id,
                row_number=row_number,
                raw_data=_serialize_raw_data(data),
                action=action,
                person_uuid=person_uuid,
                candidates=candidates,
                errors=errors or None,
                warnings=warnings or None,
            )
        )

    db.session.flush()
    job.status = ImportStatus.VALIDATED.value
    job.summary = summary
    annotate_unknown_grades(job)


def annotate_unknown_grades(job: ImportJob) -> None:
    catalog = _catalog_name_set()
    collected: dict[str, dict[str, Any]] = {}

    for row in job.rows:
        preserved = [item for item in (row.warnings or []) if not _is_unknown_grade_warning(item)]
        if row.errors:
            row.warnings = preserved or None
            continue

        unknown_in_row: list[str] = []
        for name in _row_grade_values(row.raw_data or {}):
            needle = _normalize_grade_name(name)
            if needle in catalog:
                continue
            unknown_in_row.append(name)
            entry = collected.setdefault(needle, {"name": name, "count": 0})
            entry["count"] += 1

        warnings = preserved + [_unknown_grade_warning(name) for name in unknown_in_row]
        row.warnings = warnings or None

    summary = dict(job.summary or {})
    summary["unknown_grades"] = list(collected.values())
    job.summary = summary


def _resolve_row_action(
    row: ImportRow,
    row_actions: dict[int, str | None],
) -> tuple[str | None, uuid.UUID | None]:
    chosen = row_actions.get(row.id)
    if chosen is None or chosen == "":
        return row.action, row.person_uuid

    chosen = str(chosen).strip()
    if chosen == "skip":
        return "skip", None
    if chosen == "create":
        return "create", None
    if chosen == "update":
        return "update", row.person_uuid
    if chosen.startswith("update:"):
        raw_uuid = chosen.split(":", 1)[1].strip()
        return "update", uuid.UUID(raw_uuid)
    return chosen, row.person_uuid


def _mark_row_result(row: ImportRow, result: str, message: str | None = None) -> None:
    row.result = result
    row.result_message = message


def _upsert_contract(employment: Employment, hire_date: date, contract_end: date) -> None:
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


def _upsert_grade(employment: Employment, grade_id: int, grade_date: date) -> None:
    existing = EmployeeGradeHistory.query.filter_by(
        employment_id=employment.id,
        grade_id=grade_id,
        assigned_date=grade_date,
    ).first()
    if existing:
        return
    db.session.add(
        EmployeeGradeHistory(
            employment_id=employment.id,
            grade_id=grade_id,
            assigned_date=grade_date,
        )
    )


def _upsert_passport(person: Person, passport_until: date) -> None:
    existing = Passport.query.filter_by(
        person_id=person.id,
        valid_until=passport_until,
        is_active=True,
    ).first()
    if existing:
        return
    db.session.add(
        Passport(
            person_id=person.id,
            valid_until=passport_until,
            is_active=True,
        )
    )


def confirm_import(
    job: ImportJob,
    row_actions: dict[int, str | None] | None = None,
    *,
    mark_reached_tenure: bool = True,
    update_existing_tenure: bool = False,
) -> None:
    row_actions = row_actions or {}
    report = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "tenure_marked": 0,
        "skipped_reasons": {},
    }

    def bump_skip(reason: str) -> None:
        report["skipped"] += 1
        reasons = report["skipped_reasons"]
        reasons[reason] = reasons.get(reason, 0) + 1

    try:
        for row in job.rows:
            if row.action == "error":
                report["errors"] += 1
                _mark_row_result(row, "error", "Строка содержит ошибки валидации")
                continue

            action, person_uuid = _resolve_row_action(row, row_actions)

            if action == "ambiguous":
                bump_skip("ambiguous_unresolved")
                _mark_row_result(row, "skipped", "Не выбрано действие для дубликата")
                continue

            if action == "skip":
                bump_skip("skipped_by_user")
                _mark_row_result(row, "skipped", "Пропущено пользователем")
                continue

            data = row.raw_data or {}
            hire_date = _parse_date(data.get("hire_date"))
            if not hire_date:
                bump_skip("no_hire_date")
                _mark_row_result(row, "skipped", "Некорректная дата начала работы")
                continue

            person: Person | None = None
            employment: Employment | None = None
            created = False

            if action == "update":
                if not person_uuid:
                    bump_skip("no_person")
                    _mark_row_result(row, "skipped", "Не выбран сотрудник для обновления")
                    continue
                person = Person.query.filter_by(uuid=person_uuid).first()
                if not person:
                    bump_skip("person_not_found")
                    _mark_row_result(row, "skipped", "Сотрудник для обновления не найден")
                    continue
                employment = (
                    Employment.query.filter_by(
                        person_id=person.id,
                        company_id=job.company_id,
                    )
                    .order_by(Employment.hire_date.desc())
                    .first()
                )
            elif action == "create":
                has_university = _parse_bool_optional(data.get("has_university"))
                person, employment = create_person_with_employment(
                    company_id=job.company_id,
                    full_name=str(data.get("full_name", "")),
                    hire_date=hire_date,
                    title=str(data.get("title") or "Не указана"),
                    position_grade_id=_resolve_grade_id(data.get("position_grade")),
                    has_university=bool(has_university) if has_university is not None else False,
                )
                row.person_uuid = person.uuid
                created = True
            else:
                bump_skip("unknown_action")
                _mark_row_result(row, "skipped", f"Неизвестное действие: {action}")
                continue

            if employment is None and person:
                employment = (
                    Employment.query.filter_by(person_id=person.id, company_id=job.company_id)
                    .order_by(Employment.hire_date.desc())
                    .first()
                )

            if employment is None or person is None:
                bump_skip("no_employment")
                _mark_row_result(row, "skipped", "Не найдено трудоустройство")
                continue

            university = _parse_bool_optional(data.get("has_university"))
            if university is not None:
                person.has_university = university

            contract_end = _parse_date(data.get("contract_end"))
            if contract_end:
                _upsert_contract(employment, hire_date, contract_end)

            grade_date = _parse_date(data.get("grade_date"))
            grade_id = _resolve_grade_id(data.get("actual_grade"))
            if grade_id and grade_date:
                _upsert_grade(employment, grade_id, grade_date)

            passport_until = _parse_date(data.get("passport_until"))
            if passport_until:
                _upsert_passport(person, passport_until)

            awards = ensure_tenure_awards(employment.id, employment.hire_date)
            if mark_reached_tenure and (created or update_existing_tenure):
                report["tenure_marked"] += auto_mark_reached_awards(awards)

            if created:
                report["created"] += 1
                _mark_row_result(row, "created")
            else:
                report["updated"] += 1
                _mark_row_result(row, "updated")

        preview = {
            key: (job.summary or {}).get(key, 0)
            for key in ("create", "update", "ambiguous", "error")
        }
        job.summary = {**preview, **report}
        job.status = ImportStatus.CONFIRMED.value
        job.error_message = None
        db.session.flush()
        run_rule_engine(job.company_id)
        refresh_overdue_events(job.company_id)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        job.status = ImportStatus.FAILED.value
        job.error_message = str(exc)
        db.session.commit()
        raise


def export_template(company_id: int, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    headers = [
        "№ п/п",
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
        contract = get_active_contract(employment)
        grade = get_current_grade(employment)
        passport = get_active_passport(person)

        ws.append(
            [
                idx,
                get_current_name(person),
                position.title if position else "",
                position.position_grade.name if position and position.position_grade else "",
                grade.grade.name if grade else "",
                "Да" if person.has_university else "Нет",
                format_display_date_ru(contract.end_date) if contract else "",
                format_display_date_ru(grade.assigned_date) if grade else "",
                format_display_date_ru(employment.hire_date),
                format_display_date_ru(passport.valid_until) if passport else "",
            ]
        )

    wb.save(path)


# Backward-compatible alias for older callers/tests.
export_template_with_uuids = export_template
