"""Integration checks for responsible departments and DOCX formatting."""
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from test_onboarding import data, setup_plan, patch_cell

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def test_responsible_department_lifecycle(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    assert column["responsible_department"] is None
    changed = data(hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={
        "version": column["version"], "responsible_department": "  3 отдел  ",
    }))
    assert changed["responsible_department"] == "3 отдел"
    assert data(hr_client.get("/api/onboarding/columns"))[0]["responsible_department"] == "3 отдел"
    assert hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={
        "version": column["version"], "responsible_department": "Другой",
    }).status_code == 409
    cleared = data(hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={
        "version": changed["version"], "responsible_department": "",
    }))
    assert cleared["responsible_department"] is None


def test_docx_department_is_italic_and_planned_date_kept(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    data(patch_cell(hr_client, plan, column, planned_date="2026-11-21"))
    column = data(hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={
        "version": column["version"], "responsible_department": "3 отдел", "document_stage_key": "nda",
    }))
    response = hr_client.get(f'/api/onboarding/plans/{plan["id"]}/docx')
    assert response.status_code == 200
    with ZipFile(BytesIO(response.data)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = root.findall(".//" + W + "p")
    target = next(p for p in paragraphs if "NDA" in "".join(t.text or "" for t in p.findall(".//" + W + "t")))
    runs = target.findall(W + "r")
    def text(run):
        return "".join(t.text or "" for t in run.findall(".//" + W + "t"))
    assert text(runs[0]).startswith("NDA: 21.11.2026")
    assert text(runs[-1]) == "(отв 3 отдел)"
    assert runs[0].find(W + "rPr") is None
    assert runs[-1].find(W + "rPr/" + W + "i") is not None
    assert runs[-1].find(W + "rPr/" + W + "sz").get(W + "val") == "24"
    assert runs[-1].find(W + "rPr/" + W + "rFonts").get(W + "ascii") == "Times New Roman"
    assert "21.11.2026" in "".join(text(run) for run in runs)


def test_docx_old_column_without_department(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    response = hr_client.get(f'/api/onboarding/plans/{plan["id"]}/docx')
    assert response.status_code == 200
    with ZipFile(BytesIO(response.data)) as archive:
        xml = archive.read("word/document.xml").decode()
    assert "NDA" in xml
    assert "(отв" not in xml


def test_custom_word_template_keeps_variables_and_italic_department(hr_client, seed_company, tmp_path):
    from app.services.onboarding_docx import _default_template
    plan, column = setup_plan(hr_client, seed_company.id)
    data(patch_cell(hr_client, plan, column, planned_date="2026-11-21"))
    data(hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={
        "version": column["version"], "responsible_department": "3 отдел", "document_stage_key": "nda",
    }))
    custom = tmp_path / "onboarding.docx"
    custom.write_bytes(_default_template().getvalue())
    hr_client.application.config["ONBOARDING_DOCX_TEMPLATE"] = str(custom)
    try:
        response = hr_client.get(f'/api/onboarding/plans/{plan["id"]}/docx')
        assert response.status_code == 200
        with ZipFile(BytesIO(response.data)) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        target = next(p for p in root.findall(".//" + W + "p")
                      if "NDA" in "".join(t.text or "" for t in p.findall(".//" + W + "t")))
        runs = target.findall(W + "r")
        assert "21.11.2026" in "".join(t.text or "" for t in target.findall(".//" + W + "t"))
        assert "".join(t.text or "" for t in runs[-1].findall(W + "t")) == "(отв 3 отдел)"
        assert runs[-1].find(W + "rPr/" + W + "i") is not None
    finally:
        hr_client.application.config["ONBOARDING_DOCX_TEMPLATE"] = ""


def test_word_template_department_placeholder_controls_position_and_typography():
    """The department can live independently of the date, with only its text restyled."""
    from app.services.onboarding_docx import _replace_xml
    from app.services.onboarding_document_catalog import document_variables

    variables = {key: "—" for key in document_variables()}
    variables["nda_planned_date"] = "21.11.2026"
    variables["nda_department"] = "(отв 3 отдел)"
    # Keep ordinary title text and a placeholder spread over two Word runs.
    xml = ('''<?xml version="1.0" encoding="UTF-8"?>'''
           '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'''
           '''<w:body><w:p><w:r><w:t>NDA: {{ nda_planned_date }}</w:t></w:r></w:p>'''
           '''<w:p><w:r><w:rPr><w:color w:val="FF0000"/><w:b/></w:rPr>'''
           '''<w:t xml:space="preserve">Ответственный: {{ nda_</w:t></w:r>'''
           '''<w:r><w:t>department }}!</w:t></w:r></w:p></w:body></w:document>''').encode()
    output = _replace_xml(xml, variables, {"nda": "3 отдел"}, {"nda"})
    root = ET.fromstring(output)
    paragraphs = root.findall(".//" + W + "p")
    assert len(paragraphs) == 2
    date_line = "".join(t.text or "" for t in paragraphs[0].findall(".//" + W + "t"))
    assert date_line == "NDA: 21.11.2026"

    line = paragraphs[1]
    assert "".join(t.text or "" for t in line.findall(".//" + W + "t")) == "Ответственный: (отв 3 отдел)!"
    department_run = next(
        run for run in line.findall(W + "r")
        if "(отв 3 отдел)" in "".join(t.text or "" for t in run.findall(W + "t"))
    )
    props = department_run.find(W + "rPr")
    assert props is not None
    fonts = props.find(W + "rFonts")
    assert fonts.get(W + "ascii") == "Times New Roman"
    assert fonts.get(W + "hAnsi") == "Times New Roman"
    assert fonts.get(W + "eastAsia") == "Times New Roman"
    assert props.find(W + "sz").get(W + "val") == "24"
    assert props.find(W + "szCs").get(W + "val") == "24"
    assert props.find(W + "i") is not None
    assert props.find(W + "b") is not None
    assert props.find(W + "color").get(W + "val") == "FF0000"
    # Prefix and suffix remain outside the department's formatted run.
    assert "Ответственный:" not in "".join(t.text or "" for t in department_run.findall(W + "t"))
    assert "!" not in "".join(t.text or "" for t in department_run.findall(W + "t"))


def test_word_template_without_department_variable_does_not_append_any_suffix():
    from app.services.onboarding_docx import _replace_xml

    xml = ('''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'''
           '''<w:body><w:p><w:r><w:t>NDA: {{ nda_planned_date }}</w:t></w:r></w:p>'''
           '''</w:body></w:document>''').encode()
    result = _replace_xml(xml, {"nda_planned_date": "21.11.2026"}, {"nda": "3 отдел"})
    paragraph = ET.fromstring(result).find(".//" + W + "p")
    assert "".join(t.text or "" for t in paragraph.findall(".//" + W + "t")) == "NDA: 21.11.2026"


def test_word_template_empty_department_placeholder_has_no_artificial_suffix():
    from app.services.onboarding_docx import _replace_xml
    from app.services.onboarding_document_catalog import document_variables

    variables = {key: "—" for key in document_variables()}
    variables["nda_department"] = ""
    xml = ('''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'''
           '''<w:body><w:p><w:r><w:t>{{ nda_department }}</w:t></w:r></w:p>'''
           '''</w:body></w:document>''').encode()
    result = _replace_xml(xml, variables, {}, {"nda"})
    root = ET.fromstring(result)
    assert "(отв" not in result.decode()
    assert "BOOKHR_DOCX_DEPARTMENT" not in result.decode()
    assert root.find(".//" + W + "p") is not None
