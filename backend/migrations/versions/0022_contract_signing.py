"""Persist report terms and unique signing results."""
from alembic import op
import sqlalchemy as sa
revision = "0022_contract_signing"
down_revision = "0021_onboarding_department"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("contract_renewals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_contract_id", sa.Integer(), sa.ForeignKey("contracts.id"), nullable=False, unique=True),
        sa.Column("report_event_id", sa.Integer(), sa.ForeignKey("events.id"), unique=True),
        sa.Column("signing_event_id", sa.Integer(), sa.ForeignKey("events.id"), unique=True),
        sa.Column("result_contract_id", sa.Integer(), sa.ForeignKey("contracts.id"), unique=True),
        sa.Column("source_end_date", sa.Date(), nullable=False),
        sa.Column("term_years", sa.Float()),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("term_years IS NULL OR term_years > 0", name="ck_renewal_term_positive"))

def downgrade():
    op.drop_table("contract_renewals")
