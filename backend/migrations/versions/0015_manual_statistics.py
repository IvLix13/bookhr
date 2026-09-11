"""Add manual statistics snapshots."""

from alembic import op
import sqlalchemy as sa


revision = "0015_manual_statistics"
down_revision = "0014_attestation_date"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "manual_statistics_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index(
        op.f("ix_manual_statistics_snapshots_company_id"),
        "manual_statistics_snapshots",
        ["company_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        op.f("ix_manual_statistics_snapshots_company_id"),
        table_name="manual_statistics_snapshots",
    )
    op.drop_table("manual_statistics_snapshots")
