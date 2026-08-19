"""Add status_changed_date to rewards."""

from alembic import op
import sqlalchemy as sa


revision = "0012_reward_status_changed_date"
down_revision = "0011_tenure_person_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rewards",
        sa.Column("status_changed_date", sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_column("rewards", "status_changed_date")
