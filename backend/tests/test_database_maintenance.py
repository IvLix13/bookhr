"""Maintenance previews, atomic writes, foreign keys and offline shell entrypoints."""
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import AuditLog, Company, Contract, ContractRenewal, Employment, Event, EventStatus, EventStatusHistory, NotificationDelivery, NotificationRule
from app.services.database_maintenance import EXTENSION_ACTION, extend_contracts_one_day, purge_cancelled_events
from app.services.employees import create_person_with_employment
from app.services.events import transition_event_status
from app.services.rule_engine import contract_expiry_rule_key, process_contract_rules


@pytest.fixture()
def maintenance_data(app, seed_company):
    with app.app_context():
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        _, employee = create_person_with_employment(company_id=seed_company.id, full_name="Обслуживание Тест",
            hire_date=date(2020, 1, 1), title="Инженер")
        contract = Contract(employment_id=employee.id, start_date=date(2025, 12, 1),
                            end_date=date(2027, 11, 30), term_years=2, is_active=True)
        db.session.add(contract)
        db.session.flush()
        process_contract_rules(employee)
        db.session.add(NotificationRule(company_id=seed_company.id, recipient_user_id="test", send_time_moscow="00:00"))
        process_contract_rules(employee)
        renewal = ContractRenewal.query.filter_by(source_contract_id=contract.id).one()
        unrelated = Event(company_id=seed_company.id, employment_id=employee.id, title="Не договор", event_type="manual",
                          event_date=date(2027, 11, 30), status="planned", source="manual")
        db.session.add(unrelated)
        db.session.commit()
        return contract.id, employee.id, renewal.report_event_id, renewal.signing_event_id, unrelated.id


def counts():
    return {model.__tablename__: model.query.count() for model in
            (Contract, ContractRenewal, Event, EventStatusHistory, NotificationDelivery, AuditLog)}


def test_extend_preview_only_reads(app, maintenance_data):
    with app.app_context():
        before = counts()
        result = extend_contracts_one_day()
        assert (result["applied"], result["contracts"]) == (False, 1)
        assert result["sample"] == [{"id": maintenance_data[0], "old_end": "2027-11-30", "new_end": "2027-12-01"}]
        assert counts() == before
        assert db.session.get(Contract, maintenance_data[0]).end_date == date(2027, 11, 30)


def test_extend_all_including_archive_and_other_company_reschedules_only_contracts(app, seed_company, maintenance_data):
    with app.app_context():
        other = Company(name="Вторая компания")
        db.session.add(other)
        db.session.flush()
        _, employee = create_person_with_employment(company_id=other.id, full_name="Архив Тест",
            hire_date=date(2020, 1, 1), title="Инженер")
        employee.status = "dismissed"
        archived = Contract(employment_id=employee.id, start_date=date(2026, 1, 1),
                            end_date=date(2026, 12, 31), term_years=1, is_active=False)
        leap = Contract(employment_id=employee.id, start_date=date(2027, 2, 28),
                        end_date=date(2028, 2, 28), term_years=1, is_active=False)
        db.session.add_all([archived, leap])
        source = db.session.get(Contract, maintenance_data[0])
        legacy = Event(company_id=seed_company.id, employment_id=source.employment_id,
                       title="Договор до...", event_type="contract", source="rule", status="planned",
                       reference_type="contract", reference_id=source.id, event_date=source.end_date,
                       rule_key=contract_expiry_rule_key(source))
        db.session.add(legacy)
        db.session.commit()
        original = {c.id: (c.start_date, c.term_years, c.end_date) for c in Contract.query.all()}
        result = extend_contracts_one_day(apply=True)
        db.session.commit()
        assert result["contracts"] == 3 and result["applied"] is True
        for contract in Contract.query.all():
            assert (contract.start_date, contract.term_years) == original[contract.id][:2]
            assert (contract.end_date - original[contract.id][2]).days == 1
        assert archived.end_date == date(2027, 1, 1)
        assert leap.end_date == date(2028, 2, 29)
        source = db.session.get(Contract, maintenance_data[0])
        assert ContractRenewal.query.filter_by(source_contract_id=source.id).one().source_end_date == source.end_date
        assert db.session.get(Event, maintenance_data[2]).event_date == date(2027, 8, 1)
        assert db.session.get(Event, maintenance_data[3]).event_date == date(2027, 12, 1)
        assert db.session.get(Event, maintenance_data[4]).event_date == date(2027, 11, 30)
        assert Event.query.filter_by(rule_key=contract_expiry_rule_key(source)).first() is None
        assert legacy.status == "cancelled"
        assert Event.query.filter_by(reference_type="contract", reference_id=source.id, event_type="contract", status="cancelled").count() == 1
        pending = NotificationDelivery.query.filter_by(event_id=maintenance_data[3], status="pending").all()
        assert len(pending) == 1 and pending[0].next_attempt_at.date() == date(2027, 12, 1)


@pytest.mark.parametrize("completed", [False, True])
def test_extend_keeps_manual_and_completed_report_dates_and_is_one_time(app, maintenance_data, completed):
    with app.app_context():
        report = db.session.get(Event, maintenance_data[2])
        report.manual_date = True
        report.event_date = date(2027, 9, 15)
        if completed:
            transition_event_status(report, EventStatus.COMPLETED, "Рапорт готов")
            report.completed_at = datetime(2027, 9, 15, 12, tzinfo=timezone.utc)
        db.session.commit()
        extend_contracts_one_day(apply=True)
        db.session.commit()
        assert (report.event_date, report.status) == (date(2027, 9, 15), "completed" if completed else "planned")
        if completed:
            assert report.completed_at.date() == date(2027, 9, 15)
        assert AuditLog.query.filter_by(action=EXTENSION_ACTION).count() == 1
        with pytest.raises(ValueError, match="уже выполнено"):
            extend_contracts_one_day(apply=True)
        db.session.rollback()
        assert db.session.get(Contract, maintenance_data[0]).end_date == date(2027, 12, 1)
        assert extend_contracts_one_day()["already_applied"] is True


def test_extend_reports_signed_chain_start_mismatch_without_moving_start(app, maintenance_data):
    with app.app_context():
        source = db.session.get(Contract, maintenance_data[0])
        result = Contract(employment_id=source.employment_id, start_date=date(2027, 12, 1),
                          end_date=date(2030, 12, 1), term_years=3, is_active=False)
        db.session.add(result)
        db.session.flush()
        renewal = ContractRenewal.query.filter_by(source_contract_id=source.id).one()
        renewal.result_contract_id = result.id
        renewal.term_years = 3
        db.session.commit()
        preview = extend_contracts_one_day()
        assert preview["linked_periods_start_mismatch_after"] == 1
        extend_contracts_one_day(apply=True)
        db.session.commit()
        assert source.end_date == result.start_date == date(2027, 12, 1)
        assert result.end_date == date(2030, 12, 2)
        assert renewal.source_end_date == source.end_date


def test_extend_error_rolls_back_dates_and_audit(app, maintenance_data, monkeypatch):
    def fail(_employment):
        raise RuntimeError("test failure")
    monkeypatch.setattr("app.services.database_maintenance.process_contract_rules", fail)
    with app.app_context():
        before = counts()
    result = app.test_cli_runner().invoke(args=["extend-contracts-one-day", "--yes"])
    assert result.exit_code != 0
    assert "test failure" in result.output
    with app.app_context():
        assert db.session.get(Contract, maintenance_data[0]).end_date == date(2027, 11, 30)
        assert counts() == before


def cancel_stages():
    renewal = ContractRenewal.query.one()
    for event_id in (renewal.report_event_id, renewal.signing_event_id):
        event = db.session.get(Event, event_id)
        transition_event_status(event, EventStatus.CANCELLED, "Отменено")
    db.session.commit()
    return renewal.id


def test_purge_cancelled_detaches_both_foreign_keys_and_deletes_dependents(app, maintenance_data):
    with app.app_context():
        renewal_id = cancel_stages()
        delivery = NotificationDelivery.query.filter_by(event_id=maintenance_data[2]).one()
        delivery.status = "sent"
        delivery.sent_at = datetime(2026, 11, 4, tzinfo=timezone.utc)
        db.session.commit()
        before = counts()
        preview = purge_cancelled_events()
        assert preview["events"] == 2 and preview["contract_stage_links"] == 2
        assert counts() == before
        result = purge_cancelled_events(apply=True)
        db.session.commit()
        assert result["applied"] is True
        assert result["notification_deliveries"] == 2
        renewal = db.session.get(ContractRenewal, renewal_id)
        assert (renewal.report_event_id, renewal.signing_event_id) == (None, None)
        assert db.session.get(Contract, maintenance_data[0]) is not None
        assert db.session.get(Employment, maintenance_data[1]) is not None
        assert db.session.get(Event, maintenance_data[4]).status == "planned"
        for event_id in maintenance_data[2:4]:
            assert db.session.get(Event, event_id) is None
            assert EventStatusHistory.query.filter_by(event_id=event_id).count() == 0
            assert NotificationDelivery.query.filter_by(event_id=event_id).count() == 0
        assert db.session.execute(text("PRAGMA foreign_key_check")).all() == []
        assert purge_cancelled_events(apply=True)["events"] == 0
        db.session.commit()
        # Required stages can be regenerated without dangling references.
        process_contract_rules(db.session.get(Employment, maintenance_data[1]))
        db.session.commit()
        assert Event.query.filter_by(event_type="contract_signing", status="planned").count() == 1


def test_purge_covers_all_event_types_and_preserves_other_statuses(app, seed_company):
    with app.app_context():
        for status in ("cancelled", "completed", "overdue", "planned"):
            for kind in ("manual", "grade", "contract", "report", "contract_signing"):
                db.session.add(Event(company_id=seed_company.id, title=kind, event_type=kind,
                                     event_date=date(2026, 11, 4), status=status, source="manual"))
        db.session.commit()
        result = purge_cancelled_events(apply=True)
        db.session.commit()
        assert result["events"] == 5
        assert Event.query.count() == 15
        assert Event.query.filter_by(status="cancelled").count() == 0


def test_purge_failure_rolls_back_deletes_and_foreign_keys(app, maintenance_data, monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("test audit failure")
    with app.app_context():
        renewal_id = cancel_stages()
        before = counts()
    monkeypatch.setattr("app.services.database_maintenance.log_audit", fail)
    result = app.test_cli_runner().invoke(args=["purge-cancelled-events", "--yes"])
    assert result.exit_code != 0
    with app.app_context():
        assert counts() == before
        renewal = db.session.get(ContractRenewal, renewal_id)
        assert (renewal.report_event_id, renewal.signing_event_id) == maintenance_data[2:4]


@pytest.mark.parametrize("command", ["extend-contracts-one-day", "purge-cancelled-events"])
def test_cli_defaults_to_preview_and_rejects_conflicting_flags(app, maintenance_data, command):
    with app.app_context():
        before = counts()
    result = app.test_cli_runner().invoke(args=[command])
    assert result.exit_code == 0 and "база не изменена" in result.output
    assert json.loads(result.output.splitlines()[0])["applied"] is False
    assert app.test_cli_runner().invoke(args=[command, "--yes", "--dry-run"]).exit_code != 0
    with app.app_context():
        assert counts() == before


@pytest.mark.parametrize("command", ["extend-contracts-one-day", "purge-cancelled-events"])
@pytest.mark.parametrize("target,environment", [("dev", "development"), ("prod", "production")])
def test_shell_uses_selected_environment_without_installing_packages(tmp_path, command, target, environment):
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "scripts").mkdir()
    shutil.copy(root / "scripts" / f"{command}.sh", tmp_path / "scripts")
    (tmp_path / "backend/.venv/bin").mkdir(parents=True)
    fake = tmp_path / "backend/.venv/bin/python"
    fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$APP_ENV" "$DATABASE_URL" "$PWD" "$@"\n')
    fake.chmod(0o755)
    (tmp_path / f".env.{target}").write_text(f"DATABASE_URL=sqlite:///test-{target}.db\nAPP_ENV=wrong\n")
    env = {**os.environ, "DATABASE_URL": "sqlite:///wrong-inherited.db"}
    result = subprocess.run(["bash", str(tmp_path / "scripts" / f"{command}.sh"), target, "--yes"],
                            cwd=tmp_path.parent, env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[1:] == [environment, f"sqlite:///test-{target}.db", str(tmp_path / "backend"),
                         "-m", "flask", "--app", "app:create_app", command, "--yes"]
    (tmp_path / f".env.{target}").write_text("APP_ENV=wrong\n")
    result = subprocess.run(["bash", str(tmp_path / "scripts" / f"{command}.sh"), target, "--yes"],
                            env=env, text=True, capture_output=True)
    assert result.returncode != 0 and "DATABASE_URL must be set" in result.stderr


def test_empty_database_does_not_consume_one_time_operation(app):
    with app.app_context():
        assert extend_contracts_one_day(apply=True)["applied"] is False
        db.session.commit()
        assert AuditLog.query.filter_by(action=EXTENSION_ACTION).count() == 0
