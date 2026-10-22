"""Document stage mapping and linked curator; existing names are preserved."""
from alembic import op
import sqlalchemy as sa

revision = "0020_onboarding_docx"
down_revision = "0019_onboarding_cards"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.add_column(sa.Column("document_stage_key", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_onboarding_document_stage", ["company_id", "document_stage_key"])
    with op.batch_alter_table("onboarding_plans") as batch:
        batch.add_column(sa.Column("curator_employment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_onboarding_curator", "employments", ["curator_employment_id"], ["id"], ondelete="SET NULL")
    # Do not guess links from existing titles or names: HR selects them explicitly.


def downgrade():
    bind = op.get_bind()
    for table, column in [("onboarding_columns", "document_stage_key"), ("onboarding_plans", "curator_employment_id")]:
        value = sa.table(table, sa.column(column))
        if bind.execute(sa.select(sa.func.count()).select_from(value).where(value.c[column].isnot(None))).scalar():
            raise RuntimeError("Откат запрещён: сначала сохраните и очистите сопоставления документа и кураторов")
    with op.batch_alter_table("onboarding_plans") as batch:
        batch.drop_constraint("fk_onboarding_curator", type_="foreignkey")
        batch.drop_column("curator_employment_id")
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.drop_constraint("uq_onboarding_document_stage", type_="unique")
        batch.drop_column("document_stage_key")
