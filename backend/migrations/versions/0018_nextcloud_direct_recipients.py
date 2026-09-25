"""Replace Nextcloud room recipients with direct Talk users."""

from alembic import op
import sqlalchemy as sa


revision = "0018_nextcloud_direct_recipients"
down_revision = "0017_onboarding_states"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("notification_rules") as batch_op:
        batch_op.alter_column(
            "room_token",
            new_column_name="recipient_user_id",
            existing_type=sa.String(length=128),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "room_name",
            new_column_name="recipient_display_name",
            existing_type=sa.String(length=256),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "escalation_room_token",
            new_column_name="escalation_recipient_user_id",
            existing_type=sa.String(length=128),
            existing_nullable=True,
        )
        batch_op.add_column(
            sa.Column(
                "escalation_recipient_display_name",
                sa.String(length=256),
                nullable=True,
            )
        )

    # A room token cannot be converted safely to a Nextcloud user ID. Existing
    # rules are disabled until an administrator selects recipients again.
    op.execute(
        "UPDATE notification_rules SET "
        "recipient_user_id = NULL, recipient_display_name = NULL, "
        "escalation_recipient_user_id = NULL, is_enabled = false"
    )


def downgrade():
    op.execute(
        "UPDATE notification_rules SET recipient_user_id = '' "
        "WHERE recipient_user_id IS NULL"
    )
    with op.batch_alter_table("notification_rules") as batch_op:
        batch_op.drop_column("escalation_recipient_display_name")
        batch_op.alter_column(
            "escalation_recipient_user_id",
            new_column_name="escalation_room_token",
            existing_type=sa.String(length=128),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "recipient_display_name",
            new_column_name="room_name",
            existing_type=sa.String(length=256),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "recipient_user_id",
            new_column_name="room_token",
            existing_type=sa.String(length=128),
            existing_nullable=True,
            nullable=False,
        )
