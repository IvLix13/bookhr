from datetime import date
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest

from app.extensions import db
from app.models import Company, Employment, PositionHistory, GradeCatalog, EmployeeGradeHistory
from app.models.onboarding import OnboardingPlan
from app.services.onboarding_docx import _replace_xml, W
from test_onboarding import data, employee, setup_plan, patch_cell


def text_of(response):
    assert response.status_code == 200, response.get_json()
    with ZipFile(BytesIO(response.data)) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    return '\n'.join(n.text or '' for n in root.iter(f'{{{W}}}t'))


def test_docx_saved_planned_date_and_identity(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    url = f'/api/onboarding/plans/{plan["id"]}/export-docx'
    assert 'NDA: —' in text_of(hr_client.get(url))
    column = data(hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={
        'version': 1, 'document_stage_key': 'nda', 'title': 'Другое название'}))
    cell = data(patch_cell(hr_client, plan, column, planned_date='2026-10-20', is_completed=True, completed_date='2026-10-01'))
    with hr_client.application.app_context():
        curator_id = employee(seed_company.id, 'Петров Пётр Петрович')
        db.session.add(PositionHistory(employment_id=plan['employment_id'], title='Инженер <AI> & ПО', valid_from=date(2020, 1, 1)))
        grade = GradeCatalog(name='Junior', rank=1)
        db.session.add(grade)
        db.session.flush()
        for eid in (plan['employment_id'], curator_id):
            db.session.add(EmployeeGradeHistory(employment_id=eid, grade_id=grade.id, assigned_date=date(2020, 1, 1)))
        db.session.commit()
    data(hr_client.patch(f'/api/onboarding/plans/{plan["id"]}', json={'version': 1, 'curator_employment_id': curator_id}))
    text = text_of(hr_client.get(url))
    assert 'NDA: 20.10.2026' in text and '01.10.2026' not in text
    assert 'Сотрудник: Иванов И.' in text and 'Наставник: Петров П.П.' in text
    assert 'Грейд: Junior' in text and 'Грейд наставника: Junior' in text
    assert 'Должность: Инженер <AI> & ПО' in text and '{{' not in text
    cell = data(patch_cell(hr_client, plan, column, version=cell['version'], is_not_required=True))
    assert 'NDA: —' in text_of(hr_client.get(url))
    data(patch_cell(hr_client, plan, column, version=cell['version'], is_not_required=False))
    data(hr_client.patch(f'/api/onboarding/columns/{column["id"]}', json={'version': column['version'], 'is_archived': True}))
    assert 'NDA: —' in text_of(hr_client.get(url))


def test_mapping_validation(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    url = f'/api/onboarding/columns/{column["id"]}'
    assert hr_client.patch(url, json={'version': 1, 'document_stage_key': 'unknown'}).status_code == 400
    col = data(hr_client.patch(url, json={'version': 1, 'document_stage_key': 'nda'}))
    duplicate = {'title': 'Другой', 'field_type': 'stage', 'document_stage_key': 'nda'}
    assert hr_client.post('/api/onboarding/columns', json=duplicate).status_code == 400
    assert hr_client.post('/api/onboarding/columns', json={**duplicate, 'field_type': 'date', 'document_stage_key': 'pass'}).status_code == 400
    renamed = data(hr_client.patch(url, json={'version': col['version'], 'title': 'Новое имя'}))
    assert renamed['document_stage_key'] == 'nda'
    assert hr_client.patch(url, json={'version': renamed['version'], 'field_type': 'checkbox'}).status_code == 400
    data(hr_client.patch(url, json={'version': renamed['version'], 'document_stage_key': None}))
    data(hr_client.post('/api/onboarding/columns', json=duplicate), 201)


def test_curator_access_and_revocation(hr_client, viewer_client, seed_company):
    hr_client.post('/api/login', json={'username': 'hr_user', 'password': 'secret123'})
    plan, column = setup_plan(hr_client, seed_company.id)
    with hr_client.application.app_context():
        curator_id = employee(seed_company.id, 'Viewer_User')
    url = f'/api/onboarding/plans/{plan["id"]}'
    linked = data(hr_client.patch(url, json={'version': 1, 'curator_employment_id': curator_id}))
    viewer_client.post('/api/login', json={'username': 'viewer_user', 'password': 'secret123'})
    assert data(viewer_client.get(url))['can_edit_cells'] is True
    cell = data(patch_cell(viewer_client, plan, column, planned_date='2026-10-20'))
    assert viewer_client.patch(url, json={'version': 2, 'curator_employment_id': None}).status_code == 403
    assert text_of(viewer_client.get(url + '/export-docx'))
    hr_client.post('/api/login', json={'username': 'hr_user', 'password': 'secret123'})
    unlinked = data(hr_client.patch(url, json={'version': linked['version'], 'curator_employment_id': None}))
    data(hr_client.patch(url, json={'version': unlinked['version'], 'curator_name': 'Viewer_User'}))
    viewer_client.post('/api/login', json={'username': 'viewer_user', 'password': 'secret123'})
    assert data(viewer_client.get(url))['can_edit_cells'] is False
    assert patch_cell(viewer_client, plan, column, version=cell['version'], planned_date='2026-10-21').status_code == 403


def test_curator_tenant_active_self_and_deletion(hr_client, seed_company):
    plan, column = setup_plan(hr_client, seed_company.id)
    with hr_client.application.app_context():
        other = Company(name='Other DOCX')
        db.session.add(other)
        db.session.commit()
        foreign_id = employee(other.id)
        dismissed_id = employee(seed_company.id, 'Уволенный')
        db.session.get(Employment, dismissed_id).status = 'dismissed'
        curator_id = employee(seed_company.id, 'Наставник')
        foreign_plan = OnboardingPlan(employment_id=foreign_id)
        db.session.add(foreign_plan)
        db.session.commit()
        foreign_plan_id = foreign_plan.id
    url = f'/api/onboarding/plans/{plan["id"]}'
    for invalid in (foreign_id, dismissed_id, plan['employment_id'], 999999):
        assert hr_client.patch(url, json={'version': 1, 'curator_employment_id': invalid}).status_code == 400
    assert hr_client.get(f'/api/onboarding/plans/{foreign_plan_id}/export-docx').status_code == 404
    data(hr_client.patch(url, json={'version': 1, 'curator_employment_id': curator_id}))
    assert hr_client.patch(url, json={'version': 1, 'curator_employment_id': None}).status_code == 409
    assert hr_client.delete(f'/api/employees/{curator_id}').status_code == 200
    assert data(hr_client.get(url))['curator_employment_id'] is None


def test_word_split_runs_and_template_parts(hr_client, seed_company, tmp_path):
    plan, _ = setup_plan(hr_client, seed_company.id)
    xml = f'<w:document xmlns:w="{W}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:w14="urn:test" mc:Ignorable="w14"><w:body><w:tbl><w:tr><w:tc><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>{{{{ employee_</w:t></w:r><w:r><w:t>name }}}} / {{{{ employee_grade }}}} / {{{{ employee_grade }}}}</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'.encode()
    result = _replace_xml(xml, {'employee_name': 'Иванов И.И. & <Тест>', 'employee_grade': 'Junior'})
    root = ET.fromstring(result)
    assert ''.join(root.itertext()) == 'Иванов И.И. & <Тест> / Junior / Junior'
    assert b'xmlns:w14="urn:test"' in result and root.find(f'.//{{{W}}}b') is not None
    template = tmp_path / 'plan.docx'
    with ZipFile(template, 'w') as archive:
        archive.writestr('word/document.xml', xml)
        archive.writestr('word/header1.xml', f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t>{{{{ employee_name }}}}</w:t></w:r></w:p></w:hdr>')
        archive.writestr('word/media/test.bin', b'unchanged')
    hr_client.application.config['ONBOARDING_DOCX_TEMPLATE'] = str(template)
    response = hr_client.get(f'/api/onboarding/plans/{plan["id"]}/export-docx')
    assert response.status_code == 200
    with ZipFile(BytesIO(response.data)) as archive:
        assert archive.read('word/media/test.bin') == b'unchanged'
        assert 'Иванов И.' in archive.read('word/header1.xml').decode()
    with pytest.raises(ValueError, match='Неизвестная переменная'):
        _replace_xml(xml, {})


def test_docx_migration_preserves_legacy_values():
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE companies (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE employments (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('INSERT INTO companies VALUES (1)')
        conn.exec_driver_sql('INSERT INTO employments VALUES (1)')
        with Operations.context(MigrationContext.configure(conn)):
            for name in ('0016_onboarding', '0017_onboarding_states', '0019_onboarding_cards'):
                importlib.import_module('migrations.versions.' + name).upgrade()
            conn.exec_driver_sql("INSERT INTO onboarding_plans (id,employment_id,curator_name,created_at,updated_at) VALUES (1,1,'Прежний куратор',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
            migration = importlib.import_module('migrations.versions.0020_onboarding_docx')
            migration.upgrade()
            assert conn.exec_driver_sql('SELECT curator_name,curator_employment_id,version FROM onboarding_plans').one() == ('Прежний куратор', None, 1)
            assert conn.exec_driver_sql('SELECT COUNT(*) FROM onboarding_columns').scalar() == 6
            conn.exec_driver_sql("UPDATE onboarding_columns SET document_stage_key='nda' WHERE id=4")
            with pytest.raises(RuntimeError, match='Откат запрещён'):
                migration.downgrade()
            conn.exec_driver_sql('UPDATE onboarding_columns SET document_stage_key=NULL')
            conn.exec_driver_sql('UPDATE onboarding_plans SET curator_employment_id=1')
            with pytest.raises(RuntimeError, match='Откат запрещён'):
                migration.downgrade()
            conn.exec_driver_sql('UPDATE onboarding_plans SET curator_employment_id=NULL')
            migration.downgrade()
            migration.upgrade()
            assert conn.exec_driver_sql('SELECT curator_name FROM onboarding_plans').scalar() == 'Прежний куратор'
