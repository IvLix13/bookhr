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
        "version": column["version"], "responsible_department": "3 отдел",
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
    assert text(runs[0]) == "NDA"
    assert text(runs[-1]) == " (отв 3 отдел)"
    assert runs[0].find(W + "rPr") is None
    assert runs[-1].find(W + "rPr/" + W + "i") is not None
    assert "21.11.2026" in "".join(text(run) for run in runs)


def test_docx_old_column_without_department(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    response = hr_client.get(f'/api/onboarding/plans/{plan["id"]}/docx')
    assert response.status_code == 200
    with ZipFile(BytesIO(response.data)) as archive:
        xml = archive.read("word/document.xml").decode()
    assert "NDA" in xml
    assert "(отв" not in xml
