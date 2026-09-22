"""Dateless onboarding stages and per-employee exemptions."""

from alembic import op
import sqlalchemy as sa

revision = "0017_onboarding_states"
down_revision = "0016_onboarding"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.drop_constraint("ck_onboarding_column_type", type_="check")
        batch.create_check_constraint(
            "ck_onboarding_column_type",
            "field_type IN ('text', 'date', 'stage', 'checkbox')",
        )
    with op.batch_alter_table("onboarding_cells") as batch:
        batch.add_column(sa.Column("is_not_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.drop_constraint("ck_onboarding_completion", type_="check")
        batch.create_check_constraint("ck_onboarding_completion", "is_completed OR completed_date IS NULL")
        batch.create_check_constraint("ck_onboarding_not_required", "NOT (is_completed AND is_not_required)")


def downgrade():
    bind = op.get_bind()
    columns = sa.table("onboarding_columns", sa.column("field_type", sa.String()))
    cells = sa.table("onboarding_cells", sa.column("is_not_required", sa.Boolean()),
                     sa.column("is_completed", sa.Boolean()), sa.column("completed_date", sa.Date()))
    has_checkbox = bind.execute(sa.select(sa.func.count()).select_from(columns).where(columns.c.field_type == "checkbox")).scalar()
    has_new_values = bind.execute(sa.select(sa.func.count()).select_from(cells).where(sa.or_(
        cells.c.is_not_required.is_(True),
        sa.and_(cells.c.is_completed.is_(True), cells.c.completed_date.is_(None)),
    ))).scalar()
    if has_checkbox or has_new_values:
        raise RuntimeError("Откат запрещён: есть этапы без даты или отметки «Не нужно». Сохраните и согласованно преобразуйте данные перед откатом.")
    with op.batch_alter_table("onboarding_cells") as batch:
        batch.drop_constraint("ck_onboarding_not_required", type_="check")
        batch.drop_constraint("ck_onboarding_completion", type_="check")
        batch.drop_column("is_not_required")
        batch.create_check_constraint("ck_onboarding_completion",
                                      "(is_completed AND completed_date IS NOT NULL) OR (NOT is_completed AND completed_date IS NULL)")
    with op.batch_alter_table("onboarding_columns") as batch:
        batch.drop_constraint("ck_onboarding_column_type", type_="check")
        batch.create_check_constraint("ck_onboarding_column_type", "field_type IN ('text', 'date', 'stage')")
