"""Onboarding cards: curator and explicit in-progress state."""

from alembic import op
import sqlalchemy as sa

revision = "0019_onboarding_cards"
down_revision = "0018_nextcloud_direct_recipients"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("onboarding_plans") as batch:
        batch.add_column(sa.Column("curator_name", sa.String(256), nullable=True))
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    with op.batch_alter_table("onboarding_cells") as batch:
        batch.add_column(sa.Column("is_in_progress", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_check_constraint("ck_onboarding_in_progress",
                                      "NOT (is_in_progress AND (is_completed OR is_not_required))")


def downgrade():
    bind = op.get_bind()
    plans = sa.table("onboarding_plans", sa.column("curator_name", sa.String()))
    cells = sa.table("onboarding_cells", sa.column("is_in_progress", sa.Boolean()))
    has_curators = bind.execute(sa.select(sa.func.count()).select_from(plans).where(plans.c.curator_name.isnot(None))).scalar()
    has_progress = bind.execute(sa.select(sa.func.count()).select_from(cells).where(cells.c.is_in_progress.is_(True))).scalar()
    if has_curators or has_progress:
        raise RuntimeError("Откат запрещён: есть кураторы или этапы в работе. Сохраните и согласованно преобразуйте данные перед откатом.")
    with op.batch_alter_table("onboarding_cells") as batch:
        batch.drop_constraint("ck_onboarding_in_progress", type_="check")
        batch.drop_column("is_in_progress")
    with op.batch_alter_table("onboarding_plans") as batch:
        batch.drop_column("version")
        batch.drop_column("curator_name")
