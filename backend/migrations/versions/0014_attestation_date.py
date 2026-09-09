"""Add attestation date to employments."""

from alembic import op
import sqlalchemy as sa


revision = "0014_attestation_date"
down_revision = "0013_event_manual_date"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("employments", sa.Column("attestation_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("employments", "attestation_date")
