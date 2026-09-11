"""Manual statistics Excel import/export helpers."""

from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.extensions import db
from app.models import ManualStatisticsSnapshot

SHEET_TITLE = "Ручная статистика"
LABEL_HEADER = "Показатель"
VALUE_HEADER = "Значение"


def _cell_to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return str(value).strip()


def build_manual_statistics_template() -> BytesIO:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = SHEET_TITLE
    worksheet.append([LABEL_HEADER, VALUE_HEADER])
    worksheet.freeze_panes = "A2"
    worksheet.column_dimensions["A"].width = 38
    worksheet.column_dimensions["B"].width = 24

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def parse_manual_statistics_workbook(stream: BinaryIO) -> list[dict[str, str]]:
    try:
        workbook = load_workbook(stream, read_only=True, data_only=True)
    except (InvalidFileException, OSError, ValueError) as exc:
        raise ValueError("Не удалось прочитать Excel-файл") from exc

    worksheet = workbook.active
    first_row = next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
    headers = [_cell_to_text(value) for value in first_row]
    if len(headers) < 2 or headers[0] != LABEL_HEADER or headers[1] != VALUE_HEADER:
        raise ValueError(
            f"Ожидаются колонки «{LABEL_HEADER}» и «{VALUE_HEADER}» из шаблона"
        )

    items: list[dict[str, str]] = []
    labels: set[str] = set()
    for row_number, row in enumerate(
        worksheet.iter_rows(min_row=2, max_col=2, values_only=True),
        start=2,
    ):
        label = _cell_to_text(row[0] if len(row) > 0 else None)
        value = _cell_to_text(row[1] if len(row) > 1 else None)
        if not label and not value:
            continue
        if not label:
            raise ValueError(f"В строке {row_number} не указан показатель")
        if label in labels:
            raise ValueError(f"Показатель «{label}» указан более одного раза")
        labels.add(label)
        items.append({"label": label, "value": value})

    workbook.close()
    return items


def save_manual_statistics(
    company_id: int,
    items: list[dict[str, str]],
    source_filename: str | None,
) -> ManualStatisticsSnapshot:
    snapshot = ManualStatisticsSnapshot.query.filter_by(company_id=company_id).first()
    if snapshot is None:
        snapshot = ManualStatisticsSnapshot(company_id=company_id)
        db.session.add(snapshot)

    snapshot.items = items
    snapshot.source_filename = (
        Path(source_filename).name[:255] if source_filename else None
    )
    db.session.flush()
    return snapshot


def manual_statistics_to_dict(
    snapshot: ManualStatisticsSnapshot | None,
) -> dict[str, object]:
    if snapshot is None:
        return {
            "items": [],
            "source_filename": None,
            "updated_at": None,
        }
    return {
        "items": list(snapshot.items or []),
        "source_filename": snapshot.source_filename,
        "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
    }
