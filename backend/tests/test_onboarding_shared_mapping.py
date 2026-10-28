"""Repeated document mappings preserve all eligible values and migrate safely."""
import importlib
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.extensions import db
from app.models.onboarding import OnboardingPlan
from app.services.onboarding_docx import document_context
from test_onboarding import data, setup_plan, patch_cell


def test_shared_mapping_create_update_archive_and_docx(hr_client, seed_company):
    plan, first = setup_plan(hr_client, seed_company.id)
    first = data(hr_client.patch(f'/api/onboarding/columns/{first["id"]}', json={
        'version': first['version'], 'document_stage_key': 'nda', 'responsible_department': '3 отдел'}))
    second = data(hr_client.post('/api/onboarding/columns', json={
        'title': 'Второй NDA', 'field_type': 'stage', 'document_stage_key': 'nda', 'responsible_department': 'HR'}), 201)
    third = data(hr_client.post('/api/onboarding/columns', json={
        'title': 'Третий NDA', 'field_type': 'stage', 'responsible_department': '3 отдел'}), 201)
    third = data(hr_client.patch(f'/api/onboarding/columns/{third["id"]}', json={
        'version': third['version'], 'document_stage_key': 'nda'}))
    for column, date in [(first, '2026-11-21'), (second, '2026-12-01'), (third, '2026-11-21')]:
        data(patch_cell(hr_client, plan, column, planned_date=date))
    with hr_client.application.app_context():
        values = document_context(db.session.get(OnboardingPlan, plan['id']))
        assert values['nda_planned_date'] == '21.11.2026; 01.12.2026'
        assert values['nda_department'] == '(отв 3 отдел); (отв HR)'
    response = hr_client.get(f'/api/onboarding/plans/{plan["id"]}/docx')
    assert response.status_code == 200
    with ZipFile(BytesIO(response.data)) as archive:
        xml = ET.fromstring(archive.read('word/document.xml'))
    text = ''.join(xml.itertext())
    assert '21.11.2026; 01.12.2026' in text
    assert '(отв 3 отдел); (отв HR)' in text
    data(hr_client.patch('/api/onboarding/columns/order', json={'columns': [
        {'id': c['id'], 'version': c['version']} for c in [second, first, third]]}))
    with hr_client.application.app_context():
        values = document_context(db.session.get(OnboardingPlan, plan['id']))
        assert values['nda_planned_date'] == '01.12.2026; 21.11.2026'
        assert values['nda_department'] == '(отв HR); (отв 3 отдел)'
    second = next(c for c in data(hr_client.get('/api/onboarding/columns')) if c['id'] == second['id'])
    first = next(c for c in data(hr_client.get('/api/onboarding/columns')) if c['id'] == first['id'])
    third = next(c for c in data(hr_client.get('/api/onboarding/columns')) if c['id'] == third['id'])
    # Archive retains the shared mapping but excludes its values from export.
    data(hr_client.patch(f'/api/onboarding/columns/{second["id"]}', json={
        'version': second['version'], 'is_archived': True}))
    data(patch_cell(hr_client, plan, first, version=1, planned_date='2026-11-21', is_not_required=True))
    with hr_client.application.app_context():
        values = document_context(db.session.get(OnboardingPlan, plan['id']))
        assert values['nda_planned_date'] == '21.11.2026'  # third still contributes
        assert values['nda_department'] == '(отв 3 отдел)'
    data(patch_cell(hr_client, plan, third, version=1, planned_date=None))
    with hr_client.application.app_context():
        values = document_context(db.session.get(OnboardingPlan, plan['id']))
        assert values['nda_planned_date'] == '—'
        assert values['nda_department'] == '(отв 3 отдел)'
    # Archived mapping does not reserve the document stage either.
    data(hr_client.post('/api/onboarding/columns', json={
        'title': 'Ещё NDA', 'field_type': 'stage', 'document_stage_key': 'nda'}), 201)


def test_mapping_still_validates_catalog_and_type(hr_client):
    for values in [dict(field_type='text', document_stage_key='nda'),
                   dict(field_type='stage', document_stage_key='unknown')]:
        assert hr_client.post('/api/onboarding/columns', json={'title': 'Invalid', **values}).status_code == 400


def test_shared_mapping_migration_roundtrip():
    migration = importlib.import_module('migrations.versions.0024_onboarding_shared_mapping')
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE onboarding_columns (id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, document_stage_key VARCHAR(64), CONSTRAINT uq_onboarding_document_stage UNIQUE (company_id, document_stage_key))')
        connection.exec_driver_sql("INSERT INTO onboarding_columns VALUES (1, 1, 'nda')")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            connection.exec_driver_sql("INSERT INTO onboarding_columns VALUES (2, 1, 'nda')")
            with pytest.raises(RuntimeError, match='Откат запрещён'):
                migration.downgrade()
            assert connection.exec_driver_sql('SELECT COUNT(*) FROM onboarding_columns').scalar() == 2
            connection.exec_driver_sql('DELETE FROM onboarding_columns WHERE id = 2')
            migration.downgrade()
        assert sa.inspect(connection).get_unique_constraints('onboarding_columns')[0]['name'] == 'uq_onboarding_document_stage'
