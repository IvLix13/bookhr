"""Exercise the additive migration on an existing schema without changing contracts."""
import importlib.util
from pathlib import Path
from datetime import date
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from app.extensions import db
from app.models import Contract, ContractRenewal
from app.services.employees import create_person_with_employment


def test_signing_migration_retains_existing_contract(app,seed_company):
    path=Path(__file__).parents[1]/'migrations/versions/0022_contract_signing.py'
    spec=importlib.util.spec_from_file_location('signing_migration',path)
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with app.app_context():
        _,e=create_person_with_employment(company_id=seed_company.id,full_name='История',hire_date=date(2020,1,1),title='Инженер')
        c=Contract(employment_id=e.id,start_date=date(2025,1,1),end_date=date(2027,1,1),term_years=2,is_active=True)
        db.session.add(c)
        db.session.commit()
        cid=c.id
        ContractRenewal.__table__.drop(db.engine)
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
        assert 'contract_renewals' in inspect(db.engine).get_table_names()
        assert db.session.get(Contract,cid).end_date==date(2027,1,1)
        assert ContractRenewal.query.count()==0
        with db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                migration.upgrade()
