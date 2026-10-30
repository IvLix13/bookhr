"""Flask CLI commands."""

from __future__ import annotations

import click
import json
from flask import Flask, current_app

from app.extensions import db
from app.models import Company, Event, EventStatus, Role, RoleName, User
from app.services.demo_data import seed_demo_data
from app.services.notifications import process_pending_notifications, queue_notifications_for_event
from app.services.purge_employees import purge_all_employees
from app.services.rule_engine import run_rule_engine


def register_commands(app: Flask) -> None:
    @app.cli.command("sync-staff-directory")
    @click.option("--company-id", type=click.IntRange(min=1), default=None)
    @click.option("--person-id", type=click.IntRange(min=1), default=None, help="Локальный Person.id")
    @click.option("--dry-run", is_flag=True, help="Показать изменения без записи в БД")
    def sync_staff(company_id, person_id, dry_run):
        """Синхронизировать должности и формальные отделы без изменения грейдов."""
        from app.services.staff_directory_client import StaffDirectoryError
        from app.services.staff_directory_sync import sync_staff_directory
        try:
            stats = sync_staff_directory(
                company_id=company_id, person_id=person_id, dry_run=dry_run,
                report=lambda detail: click.echo(json.dumps(detail, ensure_ascii=False)),
            )
        except StaffDirectoryError as exc:
            raise click.ClickException(exc.code) from None
        click.echo(json.dumps(stats, ensure_ascii=False))
        if stats["errors"]:
            raise click.ClickException("Синхронизация завершилась с техническими ошибками")

    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed initial data."""
        db.create_all()
        click.echo("Tables created")

    @app.cli.command("seed")
    def seed():
        """Seed roles, default company and admin user."""
        for role_name in RoleName:
            if not Role.query.filter_by(name=role_name.value).first():
                db.session.add(Role(name=role_name.value))

        company = Company.query.filter_by(name="Пилотная компания").first()
        if not company:
            company = Company(name="Пилотная компания")
            db.session.add(company)
            db.session.flush()

        admin_role = Role.query.filter_by(name=RoleName.ADMIN.value).first()
        if admin_role and not User.query.filter_by(username="admin").first():
            password = current_app.config.get("ADMIN_DEFAULT_PASSWORD", "")
            if not password:
                raise click.ClickException(
                    "ADMIN_DEFAULT_PASSWORD is not set. Add it to .env.dev / .env.prod."
                )
            admin = User(
                username="admin",
                full_name="Администратор",
                role_id=admin_role.id,
                company_id=company.id,
                must_change_password=False,
            )
            admin.set_password(password)
            db.session.add(admin)

        db.session.commit()
        click.echo("Seed completed")

    @app.cli.command("seed-demo")
    @click.option("--force", is_flag=True, help="Reload demo data even if employees already exist")
    def seed_demo(force: bool):
        """Seed demo employees, contracts, grades, passports and auto-events."""
        result = seed_demo_data(force=force)
        click.echo(f"Demo seed completed: {result}")

    @app.cli.command("diagnose-contracts")
    def diagnose_contracts():
        """Read-only diagnosis; does not infer missing signatures or fix historical dates."""
        from app.models import Contract, ContractRenewal
        from datetime import timedelta
        from app.utils.dates import calculate_contract_start
        from app.services.contracts import renewal_for
        for contract in Contract.query.order_by(Contract.id):
            boundary = contract.end_date + timedelta(days=1) if ContractRenewal.query.filter_by(result_contract_id=contract.id).first() else contract.end_date
            if contract.term_years and calculate_contract_start(boundary, contract.term_years) != contract.start_date:
                click.echo(f"Check contract {contract.id}: start={contract.start_date}, end={contract.end_date}, term={contract.term_years}")
            renewal = renewal_for(contract.id)
            if renewal and renewal.term_years is None:
                click.echo(f"Contract {contract.id}: report term requires explicit preparation")

    @app.cli.command("run-rules")
    @click.option("--company-id", type=int, default=None)
    def run_rules(company_id):
        stats = run_rule_engine(company_id)
        events_query = Event.query.filter(
            Event.status.in_([EventStatus.PLANNED.value, EventStatus.OVERDUE.value])
        )
        if company_id:
            events_query = events_query.filter(Event.company_id == company_id)
        queued = 0
        for event in events_query.all():
            queued += queue_notifications_for_event(event)
        db.session.commit()
        click.echo(
            f"Rules: {stats}, notifications queued: {queued}"
        )

    @app.cli.command("send-notifications")
    def send_notifications():
        stats = process_pending_notifications()
        db.session.commit()
        click.echo(f"Notifications: {stats}")

    @app.cli.command("purge-employees")
    @click.option(
        "--yes",
        is_flag=True,
        help="Подтвердить полное удаление всех сотрудников",
    )
    def purge_employees(yes: bool):
        """Delete all employees and related data. Grade catalog is kept."""
        if not yes:
            raise click.ClickException(
                "Операция необратима. Запустите с флагом --yes, "
                "например: flask purge-employees --yes",
            )

        result = purge_all_employees()
        click.echo(
            "Purge completed: "
            f"employments={result.employments_deleted}, "
            f"persons={result.persons_deleted}, "
            f"import_jobs={result.import_jobs_deleted}, "
            f"grade_catalog={result.grade_catalog_after}",
        )
