"""Add term_years to contracts."""

from alembic import op
import sqlalchemy as sa


revision = "0009_contract_term_years"
down_revision = "0008_user_company_scope"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("term_years", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("contracts", schema=None) as batch_op:
        batch_op.drop_column("term_years")
