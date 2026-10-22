"""Add responsible department for onboarding fields.

Revision ID: 0020_onboarding_department
Revises: 0019_onboarding_cards
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_onboarding_department"
down_revision = "0019_onboarding_cards"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.add_column(sa.Column("responsible_department", sa.String(length=256), nullable=True))

def downgrade():
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.drop_column("responsible_department")
