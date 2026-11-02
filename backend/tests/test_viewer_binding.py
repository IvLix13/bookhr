from datetime import date
from unittest.mock import patch

import pytest
from flask import g
from app.extensions import db
from app.models import User, Company, Employment, PersonNameHistory, AuditLog
from app.services.viewer_binding import auto_bind_viewer
from app.services.ldap_auth import LdapUserInfo
from test_department_calendar import employee

NAME = 'Иванов Иван Иванович'


def prepare(app, company_id, department='01'):
    with app.app_context():
        row = employee(company_id, department=department, name=NAME)
        user = User.query.filter_by(username='viewer_user').one()
        user.full_name = NAME
        db.session.commit()
        return row.id


def test_existing_session_binds_once(viewer_client, app, seed_company, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError('External HTTP call during local binding')
    monkeypatch.setattr('requests.sessions.Session.request', no_network)
    eid = prepare(app, seed_company.id)
    g.pop('_login_user', None)
    for _ in range(2):
        response = viewer_client.get('/api/me')
        assert response.status_code == 200
        assert response.get_json()['data']['calendar_access']['available'] is True
    with app.app_context():
        assert User.query.filter_by(username='viewer_user').one().employment_id == eid
        assert AuditLog.query.filter_by(action='auto_bind').count() == 1


@pytest.mark.parametrize('ldap', [False, True])
def test_successful_login_binds(ldap, viewer_client, app, seed_company):
    eid = prepare(app, seed_company.id)
    g.pop('_login_user', None)
    app.config['LDAP_ENABLED'] = ldap
    with patch('app.api.auth.authenticate_ldap_user', return_value=LdapUserInfo('viewer_user', NAME)):
        response = viewer_client.post('/api/login', json={'username':'viewer_user','password':'secret123'})
    assert response.status_code == 200
    assert response.get_json()['data']['calendar_access']['available'] is True
    with app.app_context():
        assert User.query.filter_by(username='viewer_user').one().employment_id == eid


def test_first_ldap_login_binds(viewer_client, app, seed_company):
    with app.app_context():
        row=employee(seed_company.id, name=NAME); db.session.commit(); eid=row.id
    app.config['LDAP_ENABLED'] = True
    app.config['LDAP_DEFAULT_ROLE'] = 'viewer'
    with patch('app.api.auth.authenticate_ldap_user', return_value=LdapUserInfo('new_ldap', NAME)):
        response=viewer_client.post('/api/login', json={'username':'new_ldap','password':'secret'})
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(username='new_ldap').one().employment_id == eid


@pytest.mark.parametrize('name,expected', [(NAME, True),('  ИВАНОВ  ИВАН Иванович ', True), ('Иванов И.И.',False),('Иванов Иван',False),('Иванов Иван Петрович',False),('',False)])
def test_complete_name_only(name, expected, viewer_client, app, seed_company):
    prepare(app, seed_company.id)
    with app.app_context():
        user=User.query.filter_by(username='viewer_user').one(); user.full_name=name
        assert auto_bind_viewer(user) is expected


@pytest.mark.parametrize('scenario', ['duplicate','second_employment','dismissed','other_company','historical_name','two_current_names'])
def test_ambiguous_or_ineligible_not_bound(scenario, viewer_client, app, seed_company):
    eid=prepare(app,seed_company.id)
    with app.app_context():
        row=db.session.get(Employment,eid)
        if scenario == 'duplicate': employee(seed_company.id,name=NAME)
        elif scenario == 'second_employment':
            db.session.add(Employment(person_id=row.person_id,company_id=seed_company.id,hire_date=date(2025,1,1)))
        elif scenario == 'dismissed': row.status='dismissed'
        elif scenario == 'other_company':
            company=Company(name='Other'); db.session.add(company); db.session.flush(); row.company_id=company.id
        elif scenario == 'historical_name':
            PersonNameHistory.query.filter_by(person_id=row.person_id).one().valid_to=date(2025,1,1)
        else:
            db.session.add(PersonNameHistory(person_id=row.person_id,full_name='Другое Полное Имя',valid_from=date(2025,1,1)))
        db.session.flush()
        user=User.query.filter_by(username='viewer_user').one()
        assert auto_bind_viewer(user) is False
        assert user.employment_id is None


def test_existing_binding_never_overwritten(viewer_client,app,seed_company):
    prepare(app,seed_company.id)
    with app.app_context():
        manual=employee(seed_company.id,name='Петров Пётр Петрович'); db.session.flush()
        user=User.query.filter_by(username='viewer_user').one(); user.employment_id=manual.id
        assert auto_bind_viewer(user) is False
        assert user.employment_id == manual.id


@pytest.mark.parametrize('role',['admin','hr'])
def test_other_roles_not_bound(role,viewer_client,app,seed_company):
    from app.models import Role
    prepare(app,seed_company.id)
    with app.app_context():
        dbrole=Role(name=role);db.session.add(dbrole);db.session.flush()
        user=User.query.filter_by(username='viewer_user').one();user.role_id=dbrole.id;user.role=dbrole
        assert auto_bind_viewer(user) is False
        assert user.employment_id is None


def test_invalid_password_does_not_bind(viewer_client,app,seed_company):
    prepare(app,seed_company.id)
    assert viewer_client.post('/api/login',json={'username':'viewer_user','password':'wrong'}).status_code == 401
    with app.app_context():
        assert User.query.filter_by(username='viewer_user').one().employment_id is None
