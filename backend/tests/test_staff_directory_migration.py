"""Additive migration round trip preserves existing employee history."""
import importlib.util
from pathlib import Path
from datetime import date
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
import pytest
from app.extensions import db
from app.models import Person
from app.services.employees import create_person_with_employment


def test_upgrade_and_downgrade_preserve_people_and_positions(app, seed_company):
    spec=importlib.util.spec_from_file_location('staff_migration',Path(__file__).parents[1]/'migrations/versions/0025_staff_directory_fields.py')
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with app.app_context():
        p,_=create_person_with_employment(seed_company.id,'Иванов Иван',date(2020,1,1),'Инженер')
        db.session.commit()
        pid=p.id
        db.session.remove()
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert 'cardnumber' not in [c['name'] for c in inspect(connection).get_columns('persons')]
                migration.upgrade()
                assert connection.execute(text('SELECT title FROM position_history')).scalar()=='Инженер'
        p=db.session.get(Person,pid)
        assert p.cardnumber is None and p.fio_short is None
        p.cardnumber='0001'
        db.session.commit()
        other,_=create_person_with_employment(seed_company.id,'Петров Пётр',date(2020,1,1),'Инженер')
        other.cardnumber='0001'
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_migration_compiles_for_postgresql():
    from io import StringIO
    spec=importlib.util.spec_from_file_location('staff_migration_pg',Path(__file__).parents[1]/'migrations/versions/0025_staff_directory_fields.py')
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    buffer=StringIO()
    context=MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':buffer})
    with Operations.context(context):
        migration.upgrade()
        migration.downgrade()
    sql=buffer.getvalue()
    assert 'ADD CONSTRAINT uq_persons_cardnumber UNIQUE (cardnumber)' in sql
    assert 'ADD COLUMN staff_directory_checked_at TIMESTAMP WITH TIME ZONE' in sql
    assert 'DROP CONSTRAINT uq_persons_cardnumber' in sql
