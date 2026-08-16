import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import DevelopmentConfig


def _create_legacy_schema(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE grade_catalog (
            id INTEGER PRIMARY KEY,
            name VARCHAR(64) NOT NULL UNIQUE,
            rank INTEGER NOT NULL UNIQUE,
            min_years NUMERIC(5,2) NOT NULL,
            is_active BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE persons (
            id INTEGER PRIMARY KEY,
            uuid VARCHAR(36) NOT NULL UNIQUE,
            has_university BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE employments (
            id INTEGER PRIMARY KEY,
            person_id INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            status VARCHAR(32) NOT NULL,
            hire_date DATE NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE employee_grade_history (
            id INTEGER PRIMARY KEY,
            employment_id INTEGER NOT NULL,
            grade_id INTEGER NOT NULL,
            assigned_date DATE NOT NULL,
            assigned_by_id INTEGER,
            basis TEXT,
            valid_to DATE,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        INSERT INTO grade_catalog
        VALUES (1, 'Junior', 1, 1.5, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
        INSERT INTO persons
        VALUES (
            1,
            '00000000-0000-0000-0000-000000000001',
            0,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        );
        INSERT INTO employments
        VALUES (1, 1, 1, 'active', '2020-01-01', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
        INSERT INTO employee_grade_history
        VALUES (
            1,
            1,
            1,
            '2024-01-01',
            NULL,
            NULL,
            NULL,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        );
        """
    )
    connection.commit()
    connection.close()


def test_grade_policy_migration_upgrade_backfill_and_downgrade(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    _create_legacy_schema(database_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(
        DevelopmentConfig,
        "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{database_path}",
    )

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))

    command.stamp(config, "0009_contract_term_years")
    command.upgrade(config, "head")

    connection = sqlite3.connect(database_path)
    assert connection.execute(
        "SELECT education_status FROM persons"
    ).fetchone() == ("no",)
    assert connection.execute(
        """
        SELECT rank_at_assignment, rank_started_at, required_months,
               education_status_at_rank_entry
        FROM employee_grade_history
        """
    ).fetchone() == (1, "2024-01-01", 18, "no")
    connection.execute(
        """
        INSERT INTO grade_catalog (
            id, name, rank, min_years, extra_year_without_university,
            is_active, created_at, updated_at
        )
        VALUES (2, 'Junior B', 1, 1.0, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    connection.commit()
    connection.execute("DELETE FROM grade_catalog WHERE id = 2")
    connection.commit()
    connection.close()

    command.downgrade(config, "0009_contract_term_years")

    connection = sqlite3.connect(database_path)
    person_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(persons)").fetchall()
    }
    assert "has_university" in person_columns
    assert "education_status" not in person_columns
    connection.close()
