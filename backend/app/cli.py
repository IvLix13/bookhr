"""Flask CLI commands."""

from __future__ import annotations

import click
from flask import Flask

from app.extensions import db
from app.models import Company, Event, EventStatus, Role, RoleName, User
from app.services.demo_data import seed_demo_data
from app.services.notifications import process_pending_notifications, queue_notifications_for_event
from app.services.rule_engine import run_rule_engine

DEFAULT_ADMIN_PASSWORD = "IVan1311"


def register_commands(app: Flask) -> None:
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
            admin = User(
                username="admin",
                full_name="Администратор",
                role_id=admin_role.id,
                company_id=company.id,
                must_change_password=False,
            )
            admin.set_password(DEFAULT_ADMIN_PASSWORD)
            db.session.add(admin)

        db.session.commit()
        click.echo("Seed completed")

    @app.cli.command("seed-demo")
    @click.option("--force", is_flag=True, help="Reload demo data even if employees already exist")
    def seed_demo(force: bool):
        """Seed demo employees, contracts, grades, passports and auto-events."""
        result = seed_demo_data(force=force)
        click.echo(f"Demo seed completed: {result}")

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
