"""Integration contract: identity, grades, placement, cache, dry-run and cooldown."""
from datetime import date, timedelta
import pytest
from app.extensions import db
from app.models import AuditLog, Company, EmployeeGradeHistory, Employment, Event, GradeCatalog, Person, PositionHistory, StaffDirectoryState
from app.services.employees import create_person_with_employment, get_current_position, rehire_person, update_person_name
from app.services.staff_directory_client import StaffDirectoryError
from app.services.staff_directory_sync import sync_lock, sync_staff_directory, utcnow


class Directory:
    def __init__(self, records, callback=None):
        self.records, self.callback, self.requests_made = records, callback, 0
    def __call__(self, config):
        return self
    def find_staff_by_fio(self, *parts):
        self.requests_made += 1
        if self.callback:
            self.callback()
        if isinstance(self.records, Exception):
            raise self.records
        return self.records
    def close(self):
        pass


@pytest.fixture(autouse=True)
def enable(app):
    app.config["STAFF_DIRECTORY_ENABLED"] = True


def seed(company_id=1, name="Иванов Иван Иванович"):
    return create_person_with_employment(company_id, name, date(2020,1,1), "Инженер")


def record():
    return dict(cardnumber="00123",fio_short="Иванов И.И.",position_name="Разработчик",position_short_name="Р",formal_department_short_name="2 отдел",formal_department_name="Отдел разработки")


def run(records, **kwargs):
    source = Directory(records)
    return sync_staff_directory(client_factory=source, **kwargs), source


def due(person):
    person.staff_directory_checked_at = utcnow() - timedelta(days=1)
    db.session.commit()


def test_update_preserves_both_grades_and_is_idempotent(app, seed_company):
    with app.app_context():
        person, job = seed(seed_company.id)
        grade = GradeCatalog(name="Middle", rank=2, min_years=1)
        db.session.add(grade)
        db.session.flush()
        get_current_position(job).position_grade_id = grade.id
        db.session.add(EmployeeGradeHistory(employment_id=job.id,grade_id=grade.id,assigned_date=date(2021,1,1)))
        db.session.commit()
        pid,eid,gid = person.id,job.id,grade.id
        data = dict(record(),rank="junior",rank_short="j",staff_id=456,factual_department_name="Другой отдел")
        stats,_ = run([data])
        assert stats["updated"] == 1
        person,job = db.session.get(Person,pid),db.session.get(Employment,eid)
        assert (person.cardnumber,person.fio_short) == ("00123","Иванов И.И.")
        assert job.formal_department_name == "Отдел разработки" and job.hire_date == date(2020,1,1)
        pos = get_current_position(job)
        assert (pos.title,pos.short_title,pos.position_grade_id) == ("Разработчик","Р",gid)
        actual = EmployeeGradeHistory.query.one()
        assert (actual.grade_id,actual.assigned_date,actual.valid_to) == (gid,date(2021,1,1),None)
        assert Event.query.count() == 0
        counts = PositionHistory.query.count(),AuditLog.query.count()
        due(person)
        stats,_ = run([record()])
        assert stats["unchanged"] == 1
        assert (PositionHistory.query.count(),AuditLog.query.count()) == counts


def test_cooldown_avoids_repeated_requests(app, seed_company):
    with app.app_context():
        seed(seed_company.id)
        db.session.commit()
        run([record()])
        stats,source = run([record()])
        assert stats["requests"] == source.requests_made == 0


def test_dry_run_is_read_only(app, seed_company):
    with app.app_context():
        person,_ = seed(seed_company.id)
        db.session.commit()
        pid,stamp = person.id,person.updated_at
        counts = PositionHistory.query.count(),AuditLog.query.count()
        details = []
        stats,_ = run([record()],dry_run=True,report=details.append)
        assert stats["updated"] == 1 and details[0]["after"]["cardnumber"] == "00123"
        person = db.session.get(Person,pid)
        assert person.cardnumber is None and person.staff_directory_checked_at is None and person.updated_at == stamp
        assert (PositionHistory.query.count(),AuditLog.query.count()) == counts


@pytest.mark.parametrize("records,reason", [([],"not_found"),([{"cardnumber":""}],"missing_cardnumber"),([record(),record()],"ambiguous")])
def test_identity_problems_leave_placement_intact(app, seed_company, records, reason):
    with app.app_context():
        person,job = seed(seed_company.id)
        db.session.commit()
        pid,eid = person.id,job.id
        stats,_ = run(records)
        assert stats[reason] == 1 and db.session.get(Person,pid).cardnumber is None
        assert get_current_position(db.session.get(Employment,eid)).title == "Инженер"


def test_known_number_selects_exact_match_and_never_rebinds(app, seed_company):
    with app.app_context():
        person,_ = seed(seed_company.id)
        person.cardnumber = "00123"
        db.session.commit()
        pid = person.id
        stats,_ = run([{"cardnumber":"another"},record()])
        assert stats["updated"] == 1
        due(db.session.get(Person,pid))
        stats,_ = run([{"cardnumber":"another"}])
        assert stats["cardnumber_mismatch"] == 1 and db.session.get(Person,pid).cardnumber == "00123"


def test_duplicate_local_names_are_not_bound(app, seed_company):
    with app.app_context():
        seed(seed_company.id)
        seed(seed_company.id)
        db.session.commit()
        stats,source = run([record()])
        assert stats["ambiguous_local_name"] == 2 and source.requests_made == 0
        assert Person.query.filter(Person.cardnumber.is_not(None)).count() == 0


def test_global_number_conflict(app, seed_company):
    with app.app_context():
        person,_ = seed(seed_company.id)
        other,_ = seed(seed_company.id,"Петров Пётр Петрович")
        other.cardnumber = "00123"
        db.session.commit()
        pid = person.id
        stats,_ = run([record()],person_id=pid)
        assert stats["cardnumber_conflict"] == 1
        assert db.session.get(Person,pid).cardnumber is None and Person.query.count() == 2


def test_company_filter_does_not_bypass_multiple_jobs(app, seed_company):
    with app.app_context():
        person,_ = seed(seed_company.id)
        company = Company(name="Вторая компания")
        db.session.add(company)
        db.session.flush()
        rehire_person(person,company.id,date(2024,1,1),"Аналитик")
        db.session.commit()
        stats,_ = run([record()],company_id=seed_company.id)
        assert stats["partial"] == 1 and Person.query.one().cardnumber == "00123"
        assert all(e.formal_department_name is None for e in Employment.query.all())
        assert sorted(p.title for p in PositionHistory.query.all()) == ["Аналитик","Инженер"]


def test_dismissed_history_is_not_updated(app, seed_company):
    with app.app_context():
        person,old = seed(seed_company.id)
        old.status,old.dismissal_date = "dismissed",date(2022,1,1)
        new = rehire_person(person,seed_company.id,date(2023,1,1),"Аналитик")
        db.session.commit()
        old_id,new_id = old.id,new.id
        stats,_ = run([record()])
        assert stats["updated"] == 1
        assert get_current_position(db.session.get(Employment,old_id)).title == "Инженер"
        assert get_current_position(db.session.get(Employment,new_id)).title == "Разработчик"


def test_omitted_keys_preserve_values_explicit_null_clears(app, seed_company):
    with app.app_context():
        person,job = seed(seed_company.id)
        person.fio_short,job.formal_department_name = "Старое имя","Старый отдел"
        get_current_position(job).short_title = "И"
        db.session.commit()
        pid,eid = person.id,job.id
        run([{"cardnumber":"00123","formal_department_name":None}])
        assert db.session.get(Person,pid).fio_short == "Старое имя"
        job = db.session.get(Employment,eid)
        assert job.formal_department_name is None and get_current_position(job).short_title == "И"


def test_stale_http_result_is_discarded(app, seed_company):
    with app.app_context():
        person,_ = seed(seed_company.id)
        db.session.commit()
        pid = person.id
        def change():
            update_person_name(db.session.get(Person,pid),"Новиков Иван Иванович",date.today())
            db.session.commit()
        stats = sync_staff_directory(client_factory=Directory([record()],change))
        assert stats["stale"] == 1 and db.session.get(Person,pid).cardnumber is None


def test_throttle_cooldown_is_persistent(app, seed_company):
    with app.app_context():
        seed(seed_company.id)
        db.session.commit()
        stats,_ = run(StaffDirectoryError("rate_limited",fatal=True,cooldown=7200))
        assert stats["errors"] == 1 and StaffDirectoryState.query.one().blocked_until
        stats,source = run([record()])
        assert stats["cooldown"] and source.requests_made == 0


def test_circuit_breaker(app, seed_company):
    with app.app_context():
        for name in ["Иванов Иван","Петров Пётр","Сидоров Сидор","Новиков Иван"]:
            seed(seed_company.id,name)
        db.session.commit()
        stats,source = run(StaffDirectoryError("network_error"))
        assert stats["errors"] == source.requests_made == 3
        assert PositionHistory.query.filter_by(title="Инженер").count() == 4


def test_shared_lock(app):
    with app.app_context(),sync_lock() as acquired:
        assert acquired
        stats,source = run([record()])
        assert stats["already_running"] and source.requests_made == 0


def test_disabled_is_noop(app):
    app.config["STAFF_DIRECTORY_ENABLED"] = False
    with app.app_context():
        assert sync_staff_directory(client_factory=lambda _: pytest.fail("Unexpected request"))["disabled"]


def test_postgresql_lock_released_after_failure(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import app.services.staff_directory_sync as module
    connection=MagicMock()
    connection.execute.return_value.scalar.return_value=True
    engine=MagicMock()
    engine.dialect.name='postgresql'
    engine.connect.return_value.__enter__.return_value=connection
    monkeypatch.setattr(module,'db',SimpleNamespace(engine=engine))
    with pytest.raises(RuntimeError):
        with sync_lock() as acquired:
            assert acquired
            raise RuntimeError('test')
    assert [str(c.args[0]) for c in connection.execute.call_args_list] == ['SELECT pg_try_advisory_lock(:key)','SELECT pg_advisory_unlock(:key)']
    assert connection.commit.call_count==2


def test_cli_disabled_and_invalid_configuration(app):
    app.config['STAFF_DIRECTORY_ENABLED']=False
    assert app.test_cli_runner().invoke(args=['sync-staff-directory']).exit_code==0
    app.config.update(STAFF_DIRECTORY_ENABLED=True,STAFF_DIRECTORY_BASE_URL='',STAFF_DIRECTORY_API_KEY='do-not-print')
    result=app.test_cli_runner().invoke(args=['sync-staff-directory','--dry-run'])
    assert result.exit_code!=0 and 'invalid_configuration' in result.output
    assert 'do-not-print' not in result.output


def test_160_people_once_then_cached(app, seed_company):
    with app.app_context():
        for n in range(160):
            suffix=chr(0x430+n//26)+chr(0x430+n%26)
            seed(seed_company.id,'Сотрудник Иван'+suffix)
        db.session.commit()
        class UniqueDirectory(Directory):
            def find_staff_by_fio(self,*parts):
                self.requests_made+=1
                return [dict(record(),cardnumber=str(self.requests_made).zfill(6))]
        source=UniqueDirectory([])
        stats=sync_staff_directory(client_factory=source)
        assert stats['updated']==stats['requests']==160
        assert Person.query.filter(Person.cardnumber.is_not(None)).count()==160
        stats,source=run([record()])
        assert stats['requests']==source.requests_made==0


def test_database_error_rolls_back_one_person_and_continues(app,seed_company,monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    import app.services.staff_directory_sync as module
    original=module.update_position
    calls=[]
    def fail_once(*args,**kwargs):
        calls.append(1)
        if len(calls)==1:
            raise SQLAlchemyError('test')
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'update_position',fail_once)
    with app.app_context():
        first,_=seed(seed_company.id)
        second,_=seed(seed_company.id,'Петров Пётр')
        db.session.commit()
        first_id,second_id=first.id,second.id
        stats,_=run([record()])
        assert stats['errors']==1 and stats['updated']==1
        assert db.session.get(Person,first_id).cardnumber is None
        assert db.session.get(Person,second_id).cardnumber=='00123'
