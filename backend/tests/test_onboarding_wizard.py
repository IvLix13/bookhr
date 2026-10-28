from copy import deepcopy
from datetime import date
from io import BytesIO
from zipfile import ZipFile
import pytest
from app.extensions import db
from app.models import Person, PersonNameHistory, Employment, Company
from app.models.onboarding import OnboardingPlan, OnboardingCell


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
