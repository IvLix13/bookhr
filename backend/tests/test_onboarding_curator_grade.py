"""Mentor identity and actual current grade in draft and saved Word plans."""

from datetime import date
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from app.extensions import db
from app.models import AuditLog, Company, EmployeeGradeHistory, Employment, GradeCatalog
from app.models.onboarding import OnboardingPlan
from app.services.employees import create_person_with_employment, update_person_name
from test_onboarding_wizard import prepare


def add_mentor(company_id, name='Наставник Елена', grade_name='Грейд наставника'):
    person, employment = create_person_with_employment(company_id, name, date(2020, 1, 1), 'Инженер')
    if grade_name:
        set_grade(employment.id, grade_name)
    return person, employment


def set_grade(employment_id, name):
    current = EmployeeGradeHistory.query.filter_by(employment_id=employment_id, valid_to=None).first()
    if current:
        current.valid_to = date(2026, 1, 1)
    grade = GradeCatalog(name=name, rank=GradeCatalog.query.count() + 1, min_years=1)
    db.session.add(grade)
    db.session.flush()
    db.session.add(EmployeeGradeHistory(employment_id=employment_id, grade_id=grade.id, assigned_date=date(2026, 1, 2)))
    db.session.flush()


def assert_docx_grade(response, expected):
    assert response.status_code == 200
    with ZipFile(BytesIO(response.data)) as archive:
        root = ET.fromstring(archive.read('word/document.xml'))
    paragraphs = [''.join(p.itertext()) for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')]
    assert 'Грейд наставника: ' + expected in paragraphs


def test_wizard_keeps_exact_selection_and_exports_current_grade(hr_client, seed_company):
    payload = prepare(hr_client, seed_company.id)
    with hr_client.application.app_context():
        set_grade(payload['mentor_id'], 'Выбранный наставник')
        set_grade(payload['employment_id'], 'Грейд сотрудника')
        # Equal names must not override the explicit wizard choice.
        add_mentor(seed_company.id, grade_name='Грейд однофамильца')
        db.session.commit()
    assert_docx_grade(hr_client.post('/api/onboarding/plans/draft-docx', json=payload), 'Выбранный наставник')
    with hr_client.application.app_context():
        assert OnboardingPlan.query.count() == 0
    created = hr_client.post('/api/onboarding/plans/from-wizard', json=payload)
    assert created.status_code == 201
    plan_id = created.json['data']['id']
    with hr_client.application.app_context():
        assert db.session.get(OnboardingPlan, plan_id).curator_employment_id == payload['mentor_id']
    assert_docx_grade(hr_client.get(f'/api/onboarding/plans/{plan_id}/docx'), 'Выбранный наставник')

    # Saving the same text must retain the explicit choice despite the duplicate.
    changed = hr_client.patch(f'/api/onboarding/plans/{plan_id}', json={
        'version': created.json['data']['version'], 'curator_name': '  НАСТАВНИК ЕЛЕНА  ',
    })
    assert changed.status_code == 200
    with hr_client.application.app_context():
        plan = db.session.get(OnboardingPlan, plan_id)
        assert plan.curator_employment_id == payload['mentor_id']
        mentor = db.session.get(Employment, payload['mentor_id'])
        update_person_name(mentor.person, 'Новоеимя Елена', date(2026, 1, 1))
        set_grade(mentor.id, 'Новый текущий грейд')
        db.session.commit()
    assert_docx_grade(hr_client.get(f'/api/onboarding/plans/{plan_id}/docx'), 'Новый текущий грейд')


@pytest.mark.parametrize('case, expected', [
    ('unique', 'Грейд наставника'),
    ('normalized', 'Грейд наставника'),
    ('duplicate', '—'),
    ('foreign', '—'),
    ('dismissed', '—'),
    ('initials', '—'),
    ('no_grade', '—'),
    ('self', '—'),
])
def test_legacy_plan_matches_only_unique_local_full_name(hr_client, seed_company, case, expected):
    with hr_client.application.app_context():
        _, employee = create_person_with_employment(seed_company.id, 'Сотрудник Иван', date(2020, 1, 1), 'Инженер')
        company_id = seed_company.id
        if case == 'foreign':
            other = Company(name='Другая компания')
            db.session.add(other)
            db.session.flush()
            company_id = other.id
        _, mentor = add_mentor(company_id, grade_name=None if case == 'no_grade' else 'Грейд наставника')
        name = 'Наставник Елена'
        if case == 'normalized':
            name = '  НАСТАВНИК   елена  '
        elif case == 'duplicate':
            add_mentor(company_id, grade_name='Грейд двойника')
        elif case == 'dismissed':
            mentor.status = 'dismissed'
        elif case == 'initials':
            name = 'Наставник Е.'
        elif case == 'self':
            name = 'Сотрудник Иван'
            set_grade(employee.id, 'Собственный грейд')
        plan = OnboardingPlan(employment_id=employee.id, curator_name=name)
        db.session.add(plan)
        db.session.commit()
        plan_id, version, audits = plan.id, plan.version, AuditLog.query.count()
    assert_docx_grade(hr_client.get(f'/api/onboarding/plans/{plan_id}/docx'), expected)
    with hr_client.application.app_context():
        plan = db.session.get(OnboardingPlan, plan_id)
        assert plan.curator_employment_id is None and plan.version == version
        assert AuditLog.query.count() == audits


def test_changing_and_clearing_curator_updates_link(hr_client, seed_company):
    payload = prepare(hr_client, seed_company.id)
    with hr_client.application.app_context():
        _, other = add_mentor(seed_company.id, name='Другой Пётр', grade_name='Грейд другого наставника')
        db.session.commit()
        other_id = other.id
    created = hr_client.post('/api/onboarding/plans/from-wizard', json=payload).json['data']
    plan_id, version = created['id'], created['version']
    for name, expected_id, expected_grade in [
        ('Другой Пётр', other_id, 'Грейд другого наставника'),
        ('Произвольный текст', None, '—'),
        ('Другой Пётр', other_id, 'Грейд другого наставника'),
        (None, None, '—'),
    ]:
        response = hr_client.patch(f'/api/onboarding/plans/{plan_id}', json={'version': version, 'curator_name': name})
        assert response.status_code == 200
        version = response.json['data']['version']
        with hr_client.application.app_context():
            assert db.session.get(OnboardingPlan, plan_id).curator_employment_id == expected_id
        assert_docx_grade(hr_client.get(f'/api/onboarding/plans/{plan_id}/docx'), expected_grade)


def test_explicit_foreign_link_never_exposes_grade_or_falls_back(hr_client, seed_company):
    with hr_client.application.app_context():
        _, employee = create_person_with_employment(seed_company.id, 'Сотрудник Иван', date(2020, 1, 1), 'Инженер')
        other = Company(name='Другая компания')
        db.session.add(other)
        db.session.flush()
        _, foreign = add_mentor(other.id, grade_name='Чужой грейд')
        add_mentor(seed_company.id, grade_name='Локальный грейд')
        plan = OnboardingPlan(employment_id=employee.id, curator_name='Наставник Елена', curator_employment_id=foreign.id)
        db.session.add(plan)
        db.session.commit()
        plan_id = plan.id
    assert_docx_grade(hr_client.get(f'/api/onboarding/plans/{plan_id}/docx'), '—')


def test_deleting_linked_mentor_keeps_employee_plan_exportable(hr_client, seed_company):
    payload = prepare(hr_client, seed_company.id)
    with hr_client.application.app_context():
        set_grade(payload['mentor_id'], 'Грейд удаляемого наставника')
        db.session.commit()
    created = hr_client.post('/api/onboarding/plans/from-wizard', json=payload)
    assert created.status_code == 201
    plan_id = created.json['data']['id']
    assert hr_client.delete(f'/api/employees/{payload["mentor_id"]}').status_code == 200
    assert_docx_grade(hr_client.get(f'/api/onboarding/plans/{plan_id}/docx'), '—')
    with hr_client.application.app_context():
        assert db.session.get(OnboardingPlan, plan_id).employment_id == payload['employment_id']
