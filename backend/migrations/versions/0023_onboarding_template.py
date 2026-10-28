"""Company scoped DOCX templates."""
from alembic import op
import sqlalchemy as sa
revision = "0023_onboarding_template"
down_revision = "0022_contract_signing"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("companies", sa.Column("onboarding_docx_template", sa.LargeBinary(), nullable=True))
    op.add_column("companies", sa.Column("onboarding_template_version", sa.Integer(), nullable=False, server_default="0"))

def downgrade():
    op.drop_column("companies", "onboarding_template_version")
    op.drop_column("companies", "onboarding_docx_template")
