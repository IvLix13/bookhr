import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_room_rules_are_disabled_when_migrated_to_direct_users():
    migration = importlib.import_module(
        "migrations.versions.0018_nextcloud_direct_recipients"
    )
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE notification_rules (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                event_type VARCHAR(32),
                room_token VARCHAR(128) NOT NULL,
                room_name VARCHAR(256),
                is_enabled BOOLEAN NOT NULL,
                remind_days_before INTEGER NOT NULL,
                repeat_interval_days INTEGER NOT NULL,
                overdue_interval_days INTEGER NOT NULL,
                escalation_room_token VARCHAR(128),
                escalation_after_days INTEGER,
                send_time_moscow VARCHAR(5) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO notification_rules VALUES (
                1, 1, NULL, 'old-room', 'Old room', 1,
                0, 7, 3, 'old-escalation', 5, '09:00',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

            columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(notification_rules)"
                ).all()
            }
            assert "recipient_user_id" in columns
            assert "recipient_display_name" in columns
            assert "escalation_recipient_user_id" in columns
            assert "escalation_recipient_display_name" in columns
            assert "room_token" not in columns
            assert connection.exec_driver_sql(
                """
                SELECT recipient_user_id, escalation_recipient_user_id, is_enabled
                FROM notification_rules WHERE id = 1
                """
            ).one() == (None, None, 0)

            migration.downgrade()
            downgraded = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(notification_rules)"
                ).all()
            }
            assert "room_token" in downgraded
            assert "recipient_user_id" not in downgraded
