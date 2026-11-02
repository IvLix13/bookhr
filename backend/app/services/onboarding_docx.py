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
    from app.services.department_heads import short_employee_name
    name = get_current_name(employment.person)
    position = get_current_position(employment)
    grade = get_current_grade(employment)
    return {"full_name": name or "—", "short_name": short_employee_name(employment),
            "position": position.title if position else "—", "grade": grade.grade.name if grade else "—"}


def document_context(plan):
    employee = employee_values(plan.employment)
    curator = employee_values(None)
    if plan.curator_name:
        curator.update(full_name=plan.curator_name, short_name=short_name(plan.curator_name))
    context = {f"{prefix}.{key}": value for prefix, values in [("employee", employee), ("curator", curator)] for key, value in values.items()}
    from app.services.department_heads import head_values
    _, head = head_values(plan.employment)
    for key in ("position", "short_name", "grade"):
        context[f"department_head.{key}"] = (head or {}).get(key) or "—"
    stages = document_stages()
    for key in stages:
        context[f"stages.{key}.planned_date"] = "—"
        context[f"stages.{key}.department"] = ""
    columns = OnboardingColumn.query.filter_by(company_id=plan.employment.company_id, is_archived=False, field_type="stage").order_by(OnboardingColumn.sort_order, OnboardingColumn.id).all()
    cells = {cell.column_id: cell for cell in plan.cells}
    dates = {key: [] for key in stages}
    departments = {key: [] for key in stages}
    for column in columns:
        key = column.document_stage_key
        if key not in stages:
            continue
        department = column.responsible_department
        if department and department not in departments[key]:
            departments[key].append(department)
        cell = cells.get(column.id)
        if cell and not cell.is_not_required and cell.planned_date:
            value = cell.planned_date.strftime("%d.%m.%Y")
            if value not in dates[key]:
                dates[key].append(value)
    for key in stages:
        context[f"stages.{key}.planned_date"] = "; ".join(dates[key]) or "—"
        context[f"stages.{key}.department"] = "; ".join(f"(отв {department})" for department in departments[key])
    variables = {}
    for key, source in document_variables().items():
        if source not in context:
            raise ValueError(f"Неизвестный источник переменной DOCX: {source}")
        variables[key] = context[source]
    return variables


def _department_by_stage(plan):
    columns = OnboardingColumn.query.filter_by(company_id=plan.employment.company_id, is_archived=False, field_type="stage").all()
    grouped = {}
    for col in sorted(columns, key=lambda c: (c.sort_order, c.id)):
        if col.document_stage_key and col.responsible_department:
            values = grouped.setdefault(col.document_stage_key, [])
            if col.responsible_department not in values:
                values.append(col.responsible_department)
    return {key: "; ".join(values) for key, values in grouped.items()}


def _department_run(value, prefix, inherited_properties=""):
    """Create a separate DOCX run: template run styling plus Times New Roman 12 pt italic."""
    from xml.sax.saxutils import escape

    tag = f"{prefix}:" if prefix else "w:"
    namespace = "" if prefix else f' xmlns:w="{W}"'
    # Keep other Word formatting (e.g. color or bold) from the placeholder.
    properties = inherited_properties
    for key in ("rFonts", "sz", "szCs", "i", "iCs"):
        properties = re.sub(rf"<{tag}{key}\b[^>]*/>", "", properties)
        properties = re.sub(rf"<{tag}{key}\b[^>]*>.*?</{tag}{key}>", "", properties, flags=re.DOTALL)
    properties += (
        f'<{tag}rFonts {tag}ascii="Times New Roman" {tag}hAnsi="Times New Roman" '
        f'{tag}eastAsia="Times New Roman" {tag}cs="Times New Roman"/>'
        f'<{tag}i/><{tag}iCs/><{tag}sz {tag}val="24"/><{tag}szCs {tag}val="24"/>'
    )
    return (
        f"<{tag}r{namespace}><{tag}rPr>{properties}</{tag}rPr>"
        f'<{tag}t xml:space="preserve">{escape(value)}</{tag}t></{tag}r>'
    )


def _style_department_marker(fragment, marker, value, prefix):
    """Split the original Word run, styling ONLY the replacement text."""
    tag = re.escape(prefix + ":" if prefix else "")
    text_pattern = re.compile(rf"(<{tag}t\b[^>]*>)(.*?)(</{tag}t>)", re.DOTALL)
    node = next((m for m in text_pattern.finditer(fragment) if marker in m.group(2)), None)
    if node is None:
        raise ValueError("Не удалось найти поле ответственного отдела в DOCX")

    if not value:
        return fragment[:node.start(2)] + node.group(2).replace(marker, "", 1) + fragment[node.end(2):]

    run_pattern = re.compile(rf"<{tag}r\b[^>]*>.*?</{tag}r>", re.DOTALL)
    run = next((m for m in run_pattern.finditer(fragment)
                if m.start() <= node.start() and node.end() <= m.end()), None)
    if run is None:
        raise ValueError("Не удалось определить форматирование ответственного отдела")

    original_run = run.group(0)
    open_run = re.match(rf"<{tag}r\b[^>]*>", original_run).group(0)
    before_node = fragment[run.start():node.start(2)]
    inside = node.group(2)
    position = inside.index(marker)
    before_value = inside[:position]
    after_value = inside[position + len(marker):]

    # Extract the original run properties; preserve color/bold/underline as
    # defined in Word while overriding font, font size, and italic.
    rpr = re.search(rf"<{tag}rPr\b[^>]*>(.*?)</{tag}rPr>",
                    fragment[run.start():node.start()], flags=re.DOTALL)
    original_properties = rpr.group(1) if rpr else ""
    text_open = node.group(1)
    if "xml:space=" not in text_open:
        text_open = text_open[:-1] + ' xml:space="preserve">'

    run_tag = f"{prefix + ':' if prefix else ''}r"
    prior_content = fragment[run.start() + len(open_run):node.start()]
    if rpr:
        prior_content = prior_content.replace(rpr.group(0), "", 1)
    before_run = (
        before_node + before_value + node.group(3) + f"</{run_tag}>"
        if before_value or prior_content.strip() else ""
    )
    after_content = fragment[node.end():run.end() - len(f"</{run_tag}>")]
    after_run = (
        open_run
        + (f"<{prefix + ':' if prefix else ''}rPr>{original_properties}</{prefix + ':' if prefix else ''}rPr>"
           if rpr else "")
        + text_open + after_value + fragment[node.end(2):run.end()]
        if after_value or after_content.strip() else ""
    )
    return (fragment[:run.start()] + before_run
            + _department_run(value, prefix, original_properties)
            + after_run + fragment[run.end():])


def _replace_xml(xml, variables, departments=None, explicit_department_stages=frozenset()):
    # Keep the raw Word XML and its namespace declarations (including mc:Ignorable).
    text = xml.decode("utf-8")
    prefixes = [prefix for _, (prefix, uri) in ET.iterparse(BytesIO(xml), events=("start-ns",)) if uri == W]
    prefix = prefixes[0] if prefixes else "w"
    tag = re.escape(prefix + ":" if prefix else "")
    paragraph = re.compile(rf"<{tag}p\b[^>]*>.*?</{tag}p>", re.DOTALL)
    nodes = re.compile(rf"(<{tag}t\b[^>]*>)(.*?)(</{tag}t>)", re.DOTALL)
    from xml.sax.saxutils import escape

    sources = document_variables()
    department_keys = {key for key, source in sources.items() if source.startswith("stages.") and source.endswith(".department")}

    def replace_paragraph(match):
        fragment = match.group()
        runs = list(nodes.finditer(fragment))
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

        markers = []
        for i, placeholder in reversed(list(enumerate(placeholders))):
            key = placeholder.group(1)
            if key not in variables:
                raise ValueError(f"Неизвестная переменная в DOCX: {key}")
            first = next(j for j, start in enumerate(positions)
                         if start <= placeholder.start() < start + lengths[j])
            last = next(j for j, start in enumerate(positions)
                        if start < placeholder.end() <= start + lengths[j])
            left, right = placeholder.start() - positions[first], placeholder.end() - positions[last]
            replacement = variables[key]
            if key in department_keys:
                marker = f"__BOOKHR_DOCX_DEPARTMENT_{i}__"
                markers.append((marker, replacement))
                replacement = marker
            if first == last:
                values[first] = values[first][:left] + replacement + values[first][right:]
            else:
                values[first] = values[first][:left] + replacement
                for j in range(first + 1, last):
                    values[j] = ""
                values[last] = values[last][right:]

        for node, value in reversed(list(zip(runs, values))):
            opening = node.group(1)
            if "xml:space=" not in opening:
                opening = opening[:-1] + ' xml:space="preserve">'
            value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
            fragment = fragment[:node.start()] + opening + escape(value) + node.group(3) + fragment[node.end():]

        for marker, value in markers:
            fragment = _style_department_marker(fragment, marker, value, prefix)

        return fragment

    return paragraph.sub(replace_paragraph, text).encode("utf-8")


def _default_template(departments=None):
    from xml.sax.saxutils import escape
    paragraphs = ["План ввода в должность", "Сотрудник: {{ employee_name }}", "Должность: {{ employee_position }}", "Грейд: {{ employee_grade }}", "Наставник: {{ curator_name }}", "Грейд наставника: {{ curator_grade }}", "Плановые даты этапов"]
    variables = document_variables()
    for stage, title in document_stages().items():
        variable = next((key for key, source in variables.items() if source == f"stages.{stage}.planned_date"), None)
        department_variable = next((key for key, source in variables.items() if source == f"stages.{stage}.department"), None)
        if variable and department_variable:
            paragraphs.append(f"{title}: {{{{ {variable} }}}} {{{{ {department_variable} }}}}")
        else:
            paragraphs.append(f"{title}: {{{{ {variable} }}}}" if variable else f"{title}: —")
    paragraphs.extend(["Начальник отдела", "{{ department_head_position }}", "{{ department_head_name }}", "Грейд: {{ department_head_grade }}"])
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
    departments = _department_by_stage(plan)
    source = template_source(plan.employment.company_id)
    from html import unescape

    output = BytesIO()
    with ZipFile(source) as original, ZipFile(output, "w", ZIP_DEFLATED) as result:
        # Look through all Word XML parts: placeholders may be split into
        # multiple text nodes or placed in separate paragraphs/table cells.
        department_sources = {
            key: source for key, source in document_variables().items()
            if source.startswith("stages.") and source.endswith(".department")
        }
        explicit_variables = set()
        for entry in original.infolist():
            if entry.filename.startswith("word/") and entry.filename.endswith(".xml"):
                raw = original.read(entry.filename).decode("utf-8")
                explicit_variables.update(PLACEHOLDER.findall(unescape(re.sub(r"<[^>]+>", "", raw))))
        explicit_stages = {
            department_sources[key].split(".")[1]
            for key in explicit_variables if key in department_sources
        }

        for entry in original.infolist():
            content = original.read(entry.filename)
            if entry.filename.startswith("word/") and entry.filename.endswith(".xml"):
                content = _replace_xml(content, variables, departments, explicit_stages)
            result.writestr(entry, content)
    output.seek(0)
    return output


def template_source(company_id):
    from app.models import Company
    company = Company.query.filter_by(id=company_id).first_or_404()
    if company.onboarding_docx_template is not None:
        return BytesIO(company.onboarding_docx_template)
    configured = current_app.config.get("ONBOARDING_DOCX_TEMPLATE")
    if configured:
        if not Path(configured).is_file():
            raise ValueError("Не найден настроенный DOCX-шаблон плана ввода в должность")
        return Path(configured)
    return _default_template()


def validate_template(data):
    from zipfile import BadZipFile
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("Шаблон превышает 5 МБ")
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            names = {e.filename for e in entries}
            if len(entries) > 2000 or sum(e.file_size for e in entries) > 30 * 1024 * 1024:
                raise ValueError("Слишком большой распакованный DOCX")
            if len(names) != len(entries) or not {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= names:
                raise ValueError("Некорректная структура DOCX")
            variables = {key: "" for key in document_variables()}
            for entry in entries:
                if entry.flag_bits & 1 or ".." in entry.filename.split("/") or entry.filename.startswith("/"):
                    raise ValueError("Некорректный архив DOCX")
                if entry.filename.endswith(".xml") or entry.filename.endswith(".rels"):
                    raw = archive.read(entry)
                    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                        raise ValueError("Недопустимый XML")
                    ET.fromstring(raw)
                    if entry.filename.startswith("word/") and entry.filename.endswith(".xml"):
                        _replace_xml(raw, variables)
    except (BadZipFile, ET.ParseError, UnicodeError, RuntimeError) as exc:
        raise ValueError("Повреждённый DOCX-шаблон") from exc
