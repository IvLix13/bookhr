"""Allow HR to pin a manual date on rule events."""

from alembic import op
import sqlalchemy as sa


revision = "0013_event_manual_date"
down_revision = "0012_reward_status_changed_date"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "events",
        sa.Column(
            "manual_date",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("events", "manual_date")
