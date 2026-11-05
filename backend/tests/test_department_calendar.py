from datetime import date
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
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
        assert context['department_head_name'] == 'П.Петров'
        assert context['employee_position'] == 'специалист'
        assert head_values(head)[0] == 'not_found'
        employee(seed_company.id, title='Начальник отдела тестирования')
        assert head_values(row)[0] == 'ambiguous'


@pytest.mark.parametrize('department, expected', [
    ('Отдел разработки', 'Начальник отдела разработки'),
    ('  Отдел\tразработки   программного обеспечения  ', 'Начальник отдела разработки программного обеспечения'),
    ('Управление информационных технологий', 'Начальник отдела информационных технологий'),
    (None, 'Начальник отдела разработки'),
    ('', 'Начальник отдела разработки'),
    ('   ', 'Начальник отдела разработки'),
    ('Отдел', 'Начальник отдела разработки'),
])
def test_head_formal_department_in_plan_and_docx(hr_client, seed_company, department, expected):
    with hr_client.application.app_context():
        row = employee(seed_company.id)
        # Use the head's full department, never the employee's name or the short code.
        row.formal_department_name = 'Отдел сотрудника'
        head = employee(seed_company.id, title='Начальник отдела разработки', name='Петров Пётр Петрович')
        head.formal_department_name = department
        plan = OnboardingPlan(employment_id=row.id)
        db.session.add(plan)
        db.session.commit()
        plan_id, head_id = plan.id, head.id
        db.session.expire_all()
        assert db.session.get(Employment, head_id).formal_department_name == department

    response = hr_client.get(f'/api/onboarding/plans/{plan_id}')
    assert response.status_code == 200
    assert response.get_json()['data']['department_head']['position'] == expected
    response = hr_client.get(f'/api/onboarding/plans/{plan_id}/docx')
    assert response.status_code == 200
    with ZipFile(BytesIO(response.data)) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paragraphs = [''.join(p.itertext()) for p in root.iter(namespace + 'p')]
    assert expected in paragraphs


@pytest.mark.parametrize('title, department, expected', [
    ('Инженер', 'Отдел Разработки', 'инженер разработки'),
    ('  ВЕДУЩИЙ\tИНЖЕНЕР ОТДЕЛА  ', '  Отдел\tРазработки   ПО  ', 'ведущий инженер отдела разработки по'),
    ('Инженер отдела разработки', 'Отдел РАЗРАБОТКИ', 'инженер отдела разработки'),
    ('Инженер', None, 'инженер'),
    ('Инженер', '   ', 'инженер'),
    ('Инженер', 'Отдел', 'инженер'),
    (None, 'Отдел разработки', None),
])
def test_employee_position_in_wizard_saved_plan_and_docx(hr_client, seed_company, title, department, expected):
    with hr_client.application.app_context():
        row = employee(seed_company.id, title=title or 'Специалист')
        if title is None:
            db.session.delete(PositionHistory.query.filter_by(employment_id=row.id).one())
        row.formal_department_name = department
        mentor = employee(seed_company.id, department='02', name='Наставник Елена Ивановна')
        mentor.formal_department_name = 'Отдел наставника'
        db.session.commit()
        row_id, mentor_id = row.id, mentor.id

    payload = {'employment_id': row_id, 'mentor_id': mentor_id, 'cells': []}
    preview = hr_client.post('/api/onboarding/plans/draft-docx', json=payload)
    assert preview.status_code == 200
    created = hr_client.post('/api/onboarding/plans/from-wizard', json=payload)
    assert created.status_code == 201
    plan = created.get_json()['data']
    assert plan['employee_position'] == expected
    saved = hr_client.get(f'/api/onboarding/plans/{plan["id"]}')
    assert saved.get_json()['data']['employee_position'] == expected
    document = hr_client.get(f'/api/onboarding/plans/{plan["id"]}/docx')
    assert document.status_code == 200
    for response in (preview, document):
        with ZipFile(BytesIO(response.data)) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
        namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        paragraphs = [''.join(p.itertext()) for p in root.iter(namespace + 'p')]
        assert 'Должность: ' + (expected or '—') in paragraphs

    # Formatting must not replace the original directory data in the database.
    with hr_client.application.app_context():
        assert db.session.get(Employment, row_id).formal_department_name == department
        position = PositionHistory.query.filter_by(employment_id=row_id).first()
        assert (position.title if position else None) == title


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
