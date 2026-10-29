from io import BytesIO
from app.extensions import db
from app.models import Company
from app.services.onboarding_docx import _default_template, validate_template
import pytest


def test_catalog_placeholders(hr_client):
    stages = hr_client.get('/api/onboarding/document-stages').json['data']
    assert stages[0]['date_placeholder'].startswith('{{ ')
    assert stages[0]['department_placeholder'].endswith(' }}')


def test_template_upload_version_and_invalid_file(hr_client):
    template = hr_client.get('/api/onboarding/docx-template')
    assert template.status_code == 200
    payload = template.data
    def upload(data, version):
        return hr_client.post('/api/onboarding/docx-template', data={
            'file': (BytesIO(data), 'plan.docx'), 'version': str(version)})
    assert upload(payload, 0).status_code == 200
    assert upload(payload, 0).status_code == 409
    assert upload(b'broken', 1).status_code == 400
    assert hr_client.get('/api/onboarding/docx-template').data == payload
    assert hr_client.get('/api/onboarding/docx-template/info').json['data']['version'] == 1


def test_viewer_cannot_manage_template(viewer_client):
    assert viewer_client.get('/api/onboarding/docx-template').status_code == 403
    assert viewer_client.post('/api/onboarding/docx-template').status_code == 403


def test_templates_are_company_scoped(app, hr_client, seed_company):
    with app.app_context():
        other = Company(name='Other', onboarding_docx_template=b'other bytes')
        db.session.add(other)
        db.session.commit()
    assert hr_client.get('/api/onboarding/docx-template').data != b'other bytes'


def test_validation_rejects_unknown_variable(app):
    from zipfile import ZipFile, ZIP_DEFLATED
    with app.app_context():
        source = _default_template()
        result = BytesIO()
        with ZipFile(source) as original, ZipFile(result, 'w', ZIP_DEFLATED) as out:
            for entry in original.infolist():
                out.writestr(entry, original.read(entry).replace(b'employee_name', b'unknown_variable'))
        with pytest.raises(ValueError, match='Неизвестная переменная'):
            validate_template(result.getvalue())
