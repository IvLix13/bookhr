"""Allow several application stages to share a document stage."""
from alembic import op
import sqlalchemy as sa

revision = "0024_onboarding_shared_mapping"
down_revision = "0023_onboarding_template"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.drop_constraint("uq_onboarding_document_stage", type_="unique")


def downgrade():
    bind = op.get_bind()
    duplicates = bind.execute(sa.text(
        "SELECT company_id, document_stage_key FROM onboarding_columns "
        "WHERE document_stage_key IS NOT NULL "
        "GROUP BY company_id, document_stage_key HAVING COUNT(*) > 1"
    )).first()
    if duplicates:
        raise RuntimeError("Откат запрещён: сначала устраните повторные сопоставления этапов документа")
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.create_unique_constraint("uq_onboarding_document_stage", ["company_id", "document_stage_key"])
