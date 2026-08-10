"""Add rewards table."""

from alembic import op
import sqlalchemy as sa


revision = "0003_rewards"
down_revision = "0002_user_auth_source"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rewards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employment_id", sa.Integer(), nullable=False),
        sa.Column("reward_type", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("directive_text", sa.Text(), nullable=True),
        sa.Column("delivered_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["employment_id"], ["employments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rewards_employment_id", "rewards", ["employment_id"])
    op.create_index("ix_rewards_status", "rewards", ["status"])


def downgrade():
    op.drop_index("ix_rewards_status", table_name="rewards")
    op.drop_index("ix_rewards_employment_id", table_name="rewards")
    op.drop_table("rewards")
