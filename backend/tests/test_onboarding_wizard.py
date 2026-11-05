from copy import deepcopy
from datetime import date
from io import BytesIO
from zipfile import ZipFile
import pytest
from app.extensions import db
from app.models import Person, PersonNameHistory, Employment, Company
from app.models.onboarding import OnboardingPlan, OnboardingCell
from app.services.onboarding_docx import document_context


def prepare(client, company_id):
    ids = []
    with client.application.app_context():
        for name in ['Сотрудник Иван', 'Наставник Елена']:
            person = Person()
            db.session.add(person)
            db.session.flush()
            db.session.add(PersonNameHistory(person_id=person.id, full_name=name, valid_from=date(2020, 1, 1)))
            employment = Employment(person_id=person.id, company_id=company_id, hire_date=date(2020, 1, 1))
            db.session.add(employment)
            db.session.flush()
            ids.append(employment.id)
        db.session.commit()
    columns = [client.post('/api/onboarding/columns', json={'title': f'Этап {i}', 'field_type': kind}).get_json()['data'] for i, kind in enumerate(['stage', 'checkbox', 'text'])]
    return {'employment_id': ids[0], 'mentor_id': ids[1], 'cells': [
        {'column_id': c['id'], 'column_version': c['version'], 'values': {'planned_date': '2026-11-01'} if c['field_type'] == 'stage' else {}}
        for c in columns]}


def test_preview_has_no_writes_and_creation_is_complete(hr_client, seed_company):
    payload = prepare(hr_client, seed_company.id)
    response = hr_client.post('/api/onboarding/plans/draft-docx', json=payload)
    assert response.status_code == 200
    assert 'Наставник' in ZipFile(BytesIO(response.data)).read('word/document.xml').decode()
    with hr_client.application.app_context():
        assert OnboardingPlan.query.count() == OnboardingCell.query.count() == 0
    response = hr_client.post('/api/onboarding/plans/from-wizard', json=payload)
    assert response.status_code == 201, response.get_json()
    result = response.get_json()['data']
    assert result['curator_name'] == 'Наставник Елена'
    assert len(result['cells']) == 3
    for item in payload['cells'][:2]:
        assert result['cells'][str(item['column_id'])]['is_in_progress'] is True
    assert hr_client.post('/api/onboarding/plans/from-wizard', json=payload).status_code == 409


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'version', 'self', 'invalid_date', 'late_invalid'])
def test_invalid_wizard_never_leaves_partial_plan(hr_client, seed_company, mutation):
    body = prepare(hr_client, seed_company.id)
    if mutation == 'missing': body['cells'].pop()
    if mutation == 'duplicate': body['cells'][-1] = deepcopy(body['cells'][0])
    if mutation == 'version': body['cells'][0]['column_version'] += 1
    if mutation == 'self': body['mentor_id'] = body['employment_id']
    if mutation == 'invalid_date': body['cells'][0]['values']['planned_date'] = 'bad'
    if mutation == 'late_invalid': body['cells'][-1]['values'] = {'is_completed': True}
    assert hr_client.post('/api/onboarding/plans/from-wizard', json=body).status_code in (400, 409)
    with hr_client.application.app_context():
        assert OnboardingPlan.query.count() == OnboardingCell.query.count() == 0


def test_new_column_invalidates_draft(hr_client, seed_company):
    body = prepare(hr_client, seed_company.id)
    hr_client.post('/api/onboarding/columns', json={'title': 'Новый', 'field_type': 'stage'})
    assert hr_client.post('/api/onboarding/plans/from-wizard', json=body).status_code == 409


def test_dismissed_and_foreign_mentor_rejected(hr_client, seed_company):
    body = prepare(hr_client, seed_company.id)
    with hr_client.application.app_context():
        mentor = db.session.get(Employment, body['mentor_id'])
        mentor.status = 'dismissed'
        db.session.commit()
    assert hr_client.post('/api/onboarding/plans/from-wizard', json=body).status_code == 404
    with hr_client.application.app_context():
        other = Company(name='Other')
        db.session.add(other); db.session.flush()
        mentor = db.session.get(Employment, body['mentor_id'])
        mentor.status = 'active'; mentor.company_id = other.id
        db.session.commit()
    assert hr_client.post('/api/onboarding/plans/draft-docx', json=body).status_code == 404


def test_viewer_cannot_use_wizard(viewer_client):
    for route in ['from-wizard', 'draft-docx']:
        assert viewer_client.post('/api/onboarding/plans/' + route, json={}).status_code == 403


def test_failure_during_cell_writes_rolls_back_plan(hr_client, seed_company, monkeypatch):
    import app.api.onboarding as routes
    body = prepare(hr_client, seed_company.id)
    original = routes.save_cell
    calls = []
    def fail_later(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise ValueError('Сбой записи')
        return original(*args, **kwargs)
    monkeypatch.setattr(routes, 'save_cell', fail_later)
    assert hr_client.post('/api/onboarding/plans/from-wizard', json=body).status_code == 400
    with hr_client.application.app_context():
        assert OnboardingPlan.query.count() == OnboardingCell.query.count() == 0


@pytest.mark.parametrize('previous_date', [None, '2026-11-01'])
def test_exempt_stages_survive_preview_creation_and_reopening(hr_client, seed_company, previous_date):
    body = prepare(hr_client, seed_company.id)
    stage = body['cells'][0]
    column = hr_client.patch(f"/api/onboarding/columns/{stage['column_id']}", json={
        'version': stage['column_version'], 'document_stage_key': 'nda',
        'responsible_department': 'Охрана',
    }).get_json()['data']
    stage['column_version'] = column['version']
    # A previously entered date must not leak into the preview or saved plan.
    stage['values'] = {'planned_date': previous_date, 'is_not_required': True}
    body['cells'][1]['values'] = {'is_not_required': True}
    response = hr_client.post('/api/onboarding/plans/draft-docx', json=body)
    assert response.status_code == 200
    xml = ZipFile(BytesIO(response.data)).read('word/document.xml').decode()
    assert '01.11.2026' not in xml
    assert 'План работы ввода в должность' in xml
    with hr_client.application.app_context():
        assert OnboardingPlan.query.count() == OnboardingCell.query.count() == 0
    response = hr_client.post('/api/onboarding/plans/from-wizard', json=body)
    assert response.status_code == 201, response.get_json()
    plan_id = response.get_json()['data']['id']
    result = hr_client.get(f'/api/onboarding/plans/{plan_id}').get_json()['data']
    for item in body['cells'][:2]:
        cell = result['cells'][str(item['column_id'])]
        assert cell['is_not_required'] is True
        assert not cell['is_completed'] and not cell['is_in_progress']
        assert cell['planned_date'] is cell['completed_date'] is None
    with hr_client.application.app_context():
        context = document_context(db.session.get(OnboardingPlan, plan_id))
        assert context['nda_planned_date'] == '—'
        assert context['nda_department'] == '(отв Охрана)'
    response = hr_client.get(f'/api/onboarding/plans/{plan_id}/docx')
    assert response.status_code == 200
    assert '01.11.2026' not in ZipFile(BytesIO(response.data)).read('word/document.xml').decode()


@pytest.mark.parametrize('values', [
    {}, {'is_not_required': False},
    {'is_not_required': True, 'is_completed': True},
    {'is_not_required': True, 'is_in_progress': True},
    {'is_completed': True, 'is_in_progress': True, 'planned_date': '2026-11-01', 'completed_date': '2026-11-01'},
    {'is_not_required': True, 'completed_date': '2026-11-01'},
    {'is_not_required': 'true'},
])
def test_wizard_rejects_missing_required_dates_and_conflicting_flags(hr_client, seed_company, values):
    body = prepare(hr_client, seed_company.id)
    body['cells'][0]['values'] = values
    for route in ('draft-docx', 'from-wizard'):
        assert hr_client.post(f'/api/onboarding/plans/{route}', json=body).status_code == 400
    with hr_client.application.app_context():
        assert OnboardingPlan.query.count() == OnboardingCell.query.count() == 0
