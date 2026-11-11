"""Store personal-document error snapshots per company."""

import sqlalchemy as sa
from alembic import op

revision = "0027_personal_document_errors"
down_revision = "0026_user_employment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "personal_document_errors_snapshots",
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_succeeded", sa.Boolean(), nullable=False),
        sa.Column("attempt_version", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("company_id"),
    )


def downgrade():
    op.drop_table("personal_document_errors_snapshots")
