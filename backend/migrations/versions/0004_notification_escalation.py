"""Add escalation fields to notification rules."""

from alembic import op
import sqlalchemy as sa


revision = "0004_notification_escalation"
down_revision = "0003_rewards"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notification_rules",
        sa.Column("escalation_room_token", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "notification_rules",
        sa.Column("escalation_after_days", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("notification_rules", "escalation_after_days")
    op.drop_column("notification_rules", "escalation_room_token")
