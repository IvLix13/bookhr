from datetime import date
from flask import g
from app.extensions import db
from app.models import Person, PersonNameHistory, Employment, PositionHistory, User, Event, Company
from app.services.department_heads import head_values
from app.services.onboarding_docx import document_context
from app.models.onboarding import OnboardingPlan


def employee(company, department='01', title='Специалист', name='Иванов Иван Иванович'):
    person = Person()
    db.session.add(person); db.session.flush()
    db.session.add(PersonNameHistory(person_id=person.id, full_name=name, valid_from=date(2020,1,1)))
    row = Employment(person_id=person.id, company_id=company, hire_date=date(2020,1,1), formal_department_short_name=department)
    db.session.add(row); db.session.flush()
    db.session.add(PositionHistory(employment_id=row.id, title=title, valid_from=date(2020,1,1)))
    db.session.flush()
    return row


def test_head_and_docx(app, seed_company):
    with app.app_context():
        row = employee(seed_company.id)
        employee(seed_company.id, title='Заместитель начальника отдела')
        head = employee(seed_company.id, title='НАЧАЛЬНИК отдела разработки', name='Петров Пётр Петрович')
        assert head_values(row)[1]['employment_id'] == head.id
        plan = OnboardingPlan(employment_id=row.id)
        db.session.add(plan); db.session.flush()
        context = document_context(plan)
        assert context['department_head_name'] == 'Петров П.П.'
        assert context['employee_position'] == 'Специалист'
        assert head_values(head)[0] == 'not_found'
        employee(seed_company.id, title='Начальник отдела тестирования')
        assert head_values(row)[0] == 'ambiguous'


def test_viewer_scope_and_transfer(viewer_client, app, seed_company):
    with app.app_context():
        own = employee(seed_company.id)
        other = employee(seed_company.id, '1')
        second_company = Company(name='Other'); db.session.add(second_company); db.session.flush()
        foreign = employee(second_company.id)
        user = User.query.filter_by(username='viewer_user').one(); user.employment_id = own.id
        events = [Event(company_id=e.company_id, employment_id=e.id, title='Event', event_type='manual', event_date=date(2099,1,1), status='planned') for e in (own,other,foreign)]
        db.session.add_all(events); db.session.flush()
        db.session.add(Event(company_id=seed_company.id, title='Unassigned', event_type='manual', event_date=date(2099,1,1),status='planned'))
        ids = [e.id for e in events]; own_id=own.id
        db.session.commit()
    g.pop("_login_user", None)
    for url in ('/api/events','/api/events/upcoming'):
        data=viewer_client.get(url).get_json()['data']
        items=data['items'] if isinstance(data,dict) else data
        assert [e['id'] for e in items] == [ids[0]]
    assert viewer_client.get(f'/api/events/{ids[0]}').status_code == 200
    for id_ in ids[1:]: assert viewer_client.get(f'/api/events/{id_}').status_code == 404
    assert viewer_client.patch(f'/api/events/{ids[0]}', json={'title':'Changed'}).status_code == 403
    assert viewer_client.get('/api/events?company_id=999&department=1').get_json()['data']['total'] == 1
    assert set(viewer_client.get('/api/attention?categories=grades,tenure').get_json()['data']['counts']) == {'events'}
    with app.app_context():
        db.session.get(Employment,own_id).formal_department_short_name=None; db.session.commit()
    g.pop("_login_user", None)
    assert viewer_client.get('/api/events').get_json()['data']['total'] == 0
    assert viewer_client.get(f'/api/events/{ids[0]}').status_code == 404


def test_binding_validation(admin_client, app, seed_company):
    with app.app_context():
        row=employee(seed_company.id); row_id=row.id
        user=User.query.filter_by(username='admin_user').one(); uid=user.id
        db.session.commit()
    assert admin_client.patch(f'/api/users/{uid}', json={'employment_id':row_id}).status_code == 200
    assert admin_client.patch(f'/api/users/{uid}', json={'employment_id':True}).status_code == 400
    assert admin_client.patch(f'/api/users/{uid}', json={'employment_id':None}).get_json()['data']['employment_id'] is None


def test_migration_roundtrip():
    import importlib
    import sqlalchemy as sa
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    module=importlib.import_module('migrations.versions.0026_user_employment')
    engine=sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(sa.text('CREATE TABLE employments (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        connection.execute(sa.text('INSERT INTO users VALUES (1)'))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert connection.execute(sa.text('SELECT employment_id FROM users')).scalar() is None
            module.downgrade()
        assert [c['name'] for c in sa.inspect(connection).get_columns('users')] == ['id']
