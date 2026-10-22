"""Offline DOCX export using only the standard library and saved planned dates.

Only {{ variable }} placeholders are supported, not arbitrary template code.
Replacements span Word text runs, including tables, headers and footers.
"""
from io import BytesIO
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from flask import current_app

from app.models.onboarding import OnboardingColumn
from app.services.employees import get_current_grade, get_current_name, get_current_position
from app.services.onboarding_document_catalog import document_stages, document_variables

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PLACEHOLDER = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


def short_name(name):
    parts = (name or "").split()
    return parts[0] + (" " + "".join(p[0] + "." for p in parts[1:]) if len(parts) > 1 else "") if parts else "—"


def employee_values(employment):
    if employment is None:
        return {key: "—" for key in ("short_name", "full_name", "position", "grade")}
    name = get_current_name(employment.person)
    position = get_current_position(employment)
    grade = get_current_grade(employment)
    return {"full_name": name or "—", "short_name": short_name(name),
            "position": position.title if position else "—", "grade": grade.grade.name if grade else "—"}


def document_context(plan):
    employee = employee_values(plan.employment)
    curator = employee_values(None)
    if plan.curator_name:
        curator.update(full_name=plan.curator_name, short_name=short_name(plan.curator_name))
    context = {f"{prefix}.{key}": value for prefix, values in [("employee", employee), ("curator", curator)] for key, value in values.items()}
    stages = document_stages()
    for key in stages:
        context[f"stages.{key}.planned_date"] = "—"
    columns = OnboardingColumn.query.filter_by(company_id=plan.employment.company_id, is_archived=False, field_type="stage").all()
    cells = {cell.column_id: cell for cell in plan.cells}
    for column in columns:
        cell = cells.get(column.id)
        if column.document_stage_key in stages and cell and not cell.is_not_required and cell.planned_date:
            context[f"stages.{column.document_stage_key}.planned_date"] = cell.planned_date.strftime("%d.%m.%Y")
    variables = {}
    for key, source in document_variables().items():
        if source not in context:
            raise ValueError(f"Неизвестный источник переменной DOCX: {source}")
        variables[key] = context[source]
    return variables


def _department_by_stage(plan):
    columns = OnboardingColumn.query.filter_by(company_id=plan.employment.company_id, is_archived=False, field_type="stage").all()
    return {col.document_stage_key: col.responsible_department for col in columns if col.document_stage_key and col.responsible_department}


def _replace_xml(xml, variables, departments=None):
    # Use raw XML text replacement after locating w:t spans. This preserves
    # declarations used only by mc:Ignorable and all unrelated template markup.
    text = xml.decode("utf-8")
    prefixes = [prefix for _, (prefix, uri) in ET.iterparse(BytesIO(xml), events=("start-ns",)) if uri == W]
    prefix = prefixes[0] if prefixes else "w"
    tag = re.escape(prefix + ":" if prefix else "")
    paragraph = re.compile(rf"<{tag}p\b[^>]*>.*?</{tag}p>", re.DOTALL)
    nodes = re.compile(rf"(<{tag}t\b[^>]*>)(.*?)(</{tag}t>)", re.DOTALL)
    from xml.sax.saxutils import escape

    def replace_paragraph(match):
        fragment = match.group()
        runs = list(nodes.finditer(fragment))
        # XML parser handles numeric entities too, without changing template XML.
        values = [ET.fromstring(f'<t>{n.group(2)}</t>').text or "" for n in runs]
        lengths = [len(value) for value in values]
        joined = "".join(values)
        positions = []
        offset = 0
        for value in values:
            positions.append(offset)
            offset += len(value)
        placeholders = list(PLACEHOLDER.finditer(joined))
        if not placeholders:
            return fragment
        stage_key = None
        for stage in (departments or {}):
            for variable, source in document_variables().items():
                if source == f"stages.{stage}.planned_date" and any(p.group(1) == variable for p in placeholders):
                    stage_key = stage
                    break
            if stage_key:
                break
        for placeholder in reversed(placeholders):
            key = placeholder.group(1)
            if key not in variables:
                raise ValueError(f"Неизвестная переменная в DOCX: {key}")
            first = next(i for i, start in enumerate(positions) if start <= placeholder.start() < start + lengths[i])
            last = next(i for i, start in enumerate(positions) if start < placeholder.end() <= start + lengths[i])
            left, right = placeholder.start() - positions[first], placeholder.end() - positions[last]
            if first == last:
                values[first] = values[first][:left] + variables[key] + values[first][right:]
            else:
                values[first] = values[first][:left] + variables[key]
                for i in range(first + 1, last):
                    values[i] = ""
                values[last] = values[last][right:]
        for node, value in reversed(list(zip(runs, values))):
            opening = node.group(1)
            if "xml:space=" not in opening:
                opening = opening[:-1] + ' xml:space="preserve">'
            # Strip control characters prohibited by XML 1.0.
            value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
            fragment = fragment[:node.start()] + opening + escape(value) + node.group(3) + fragment[node.end():]
        if stage_key:
            from xml.sax.saxutils import escape as _escape
            suffix = " (отв " + departments[stage_key] + ")"
            fragment = fragment.rsplit(f"</{prefix}:p>", 1)[0] + f"<{prefix}:r><{prefix}:rPr><{prefix}:i/></{prefix}:rPr><{prefix}:t xml:space=\"preserve\">{_escape(suffix)}</{prefix}:t></{prefix}:r></{prefix}:p>"
        return fragment

    return paragraph.sub(replace_paragraph, text).encode("utf-8")


def _default_template(departments=None):
    from xml.sax.saxutils import escape
    paragraphs = ["План ввода в должность", "Сотрудник: {{ employee_name }}", "Должность: {{ employee_position }}", "Грейд: {{ employee_grade }}", "Наставник: {{ curator_name }}", "Грейд наставника: {{ curator_grade }}", "Плановые даты этапов"]
    variables = document_variables()
    for stage, title in document_stages().items():
        variable = next((key for key, source in variables.items() if source == f"stages.{stage}.planned_date"), None)
        paragraphs.append(f"{title}: {{{{ {variable} }}}}" if variable else f"{title}: —")
    body = ''.join(f'<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>' for p in paragraphs)
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>'
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", document)
    stream.seek(0)
    return stream


def build_onboarding_document(plan):
    variables = document_context(plan)
    configured = current_app.config.get("ONBOARDING_DOCX_TEMPLATE")
    if configured and not Path(configured).is_file():
        raise ValueError("Не найден настроенный DOCX-шаблон плана ввода в должность")
    departments = _department_by_stage(plan)
    source = Path(configured) if configured else _default_template(departments)
    output = BytesIO()
    with ZipFile(source) as original, ZipFile(output, "w", ZIP_DEFLATED) as result:
        for entry in original.infolist():
            content = original.read(entry.filename)
            if entry.filename.startswith("word/") and entry.filename.endswith(".xml"):
                content = _replace_xml(content, variables, departments)
            result.writestr(entry, content)
    output.seek(0)
    return output
