"""Directory fields through existing employee CRUD and server-side table sorting."""
from app.extensions import db
from app.models import Company, Employment
from app.services.employees import get_current_position, rehire_person, update_position
from datetime import date


def create(client, name="Иванов Иван", **fields):
    return client.post('/api/employees',json=dict(full_name=name,title='Инженер',hire_date='2020-01-01',education_status='yes',**fields))


def test_create_alias_and_patch_preserve_short_position(hr_client):
    r = hr_client.post('/api/employees',json=dict(full_name='Иванов Иван',position_name='Разработчик',position_short_name='Р',cardnumber='00007',fio_short='Иванов И.',formal_department_short_name='2 отдел',formal_department_name='Второй отдел',hire_date='2020-01-01',education_status='yes'))
    assert r.status_code == 201
    row = r.get_json()['data']
    assert row['title'] == row['position_name'] == 'Разработчик'
    assert row['cardnumber'] == '00007' and row['position_short_name'] == 'Р'
    eid = row['id']
    updated = hr_client.patch(f'/api/employees/{eid}',json={'title':'Ведущий разработчик'})
    assert updated.status_code == 200 and updated.get_json()['data']['position_short_name'] == 'Р'
    cleared = hr_client.patch(f'/api/employees/{eid}',json={'position_short_name':None})
    assert cleared.status_code == 200 and cleared.get_json()['data']['position_short_name'] is None
    conflict = hr_client.patch(f'/api/employees/{eid}',json={'title':'Инженер','position_name':'Директор'})
    assert conflict.status_code == 400


def test_cardnumber_is_globally_unique_and_old_fields_remain_optional(hr_client):
    assert create(hr_client,cardnumber='001').status_code == 201
    r = create(hr_client,name='Петров Пётр',cardnumber='001')
    assert r.status_code == 409
    r = create(hr_client,name='Сидоров Сидор')
    assert r.status_code == 201 and r.get_json()['data']['cardnumber'] is None


def test_department_sorting_applies_before_pagination_and_nulls_last(hr_client):
    for name,short,full in [('Иванов Иван',None,'А отдел'),('Петров Пётр','Я отдел',None),('Сидоров Сидор',None,None)]:
        assert create(hr_client,name=name,formal_department_short_name=short,formal_department_name=full).status_code == 201
    r = hr_client.get('/api/employees?sort=formal_department_short_name&direction=desc&per_page=1&page=1')
    assert r.status_code == 200 and r.get_json()['data']['items'][0]['full_name'] == 'Петров Пётр'
    r = hr_client.get('/api/employees?sort=formal_department_short_name&direction=desc&per_page=1&page=3')
    assert r.get_json()['data']['items'][0]['full_name'] == 'Сидоров Сидор'


def test_viewer_cannot_write_directory_fields(viewer_client):
    assert create(viewer_client,cardnumber='001').status_code == 403


def test_manual_position_and_rehire_keep_short_title(app, seed_company):
    from app.services.employees import create_person_with_employment
    with app.app_context():
        p,e = create_person_with_employment(seed_company.id,'Иванов Иван',date(2020,1,1),'Инженер')
        get_current_position(e).short_title='И'
        db.session.commit()
        update_position(e,'Старший инженер',None,date(2021,1,1))
        db.session.flush()
        assert get_current_position(e).short_title=='И'
        e.status='dismissed'
        e.dismissal_date=date(2022,1,1)
        new = rehire_person(p,seed_company.id,date(2023,1,1),'Инженер')
        db.session.flush()
        assert get_current_position(new).short_title=='И'
