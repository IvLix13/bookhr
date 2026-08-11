"""Add candidates/result fields to import_rows."""

from alembic import op
import sqlalchemy as sa


revision = "0005_import_row_result"
down_revision = "0004_notification_escalation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("import_rows", sa.Column("candidates", sa.JSON(), nullable=True))
    op.add_column("import_rows", sa.Column("result", sa.String(length=32), nullable=True))
    op.add_column("import_rows", sa.Column("result_message", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("import_rows", "result_message")
    op.drop_column("import_rows", "result")
    op.drop_column("import_rows", "candidates")
