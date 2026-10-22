"""Generate an onboarding DOCX without external document libraries.

The generated document lists all active configured onboarding points.
Only the department annotation is italic, not the point title or its date.
"""
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from app.models.onboarding import OnboardingColumn
from app.services.onboarding import current_plan_name, plan_dict
from app.services.employees import get_current_position

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _run(text, italic=False):
    properties = "<w:rPr><w:i/></w:rPr>" if italic else ""
    return '<w:r>' + properties + '<w:t xml:space="preserve">' + escape(str(text)) + '</w:t></w:r>'


def _paragraph(*runs):
    return "<w:p>" + "".join(runs) + "</w:p>"


def _short_name(name):
    parts = (name or "").split()
    return parts[0] + " " + "".join(part[0] + "." for part in parts[1:]) if parts else "—"


def build_onboarding_document(plan):
    """Return an in-memory DOCX containing planned dates and responsible departments."""
    data = plan_dict(plan)
    columns = (OnboardingColumn.query.filter_by(
        company_id=plan.employment.company_id, is_archived=False
    ).order_by(OnboardingColumn.sort_order, OnboardingColumn.id).all())
    position = get_current_position(plan.employment)
    paragraphs = [
        _paragraph(_run("План ввода в должность")),
        _paragraph(_run("Сотрудник: " + _short_name(current_plan_name(plan)))),
        _paragraph(_run("Должность: " + (position.title if position else "—"))),
        _paragraph(_run("Грейд: " + (data.get("grade") or "—"))),
        _paragraph(_run("Куратор: " + _short_name(data.get("curator_name")))),
        _paragraph(_run("Этапы и поля")),
    ]
    for column in columns:
        cell = next((cell for cell in plan.cells if cell.column_id == column.id), None)
        parts = [_run(column.title)]
        if column.responsible_department:
            parts.append(_run(" (отв " + column.responsible_department + ")", italic=True))
        if column.field_type == "stage":
            planned = cell.planned_date.strftime("%d.%m.%Y") if cell and cell.planned_date and not cell.is_not_required else "—"
            parts.append(_run(": " + planned))
        elif column.field_type == "date":
            parts.append(_run(": " + cell.date_value.strftime("%d.%m.%Y") if cell and cell.date_value else ": —"))
        elif column.field_type == "text":
            parts.append(_run(": " + (cell.text_value if cell and cell.text_value else "—")))
        paragraphs.append(_paragraph(*parts))
    body = "".join(paragraphs)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="' + W + '"><w:body>' + body +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
                '</w:body></w:document>')
    result = BytesIO()
    with ZipFile(result, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
        archive.writestr("word/document.xml", document)
    result.seek(0)
    return result
