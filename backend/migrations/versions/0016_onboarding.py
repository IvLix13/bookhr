"""Configurable onboarding plans."""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0016_onboarding"
down_revision = "0015_manual_statistics"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    columns = op.create_table(
        "onboarding_columns",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("field_type", sa.String(16), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("is_archived", sa.Boolean, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        *timestamps(),
        sa.CheckConstraint("field_type IN ('text', 'date', 'stage')", name="ck_onboarding_column_type"),
    )
    op.create_index("ix_onboarding_columns_company_id", "onboarding_columns", ["company_id"])
    op.create_table(
        "onboarding_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employment_id", sa.Integer, sa.ForeignKey("employments.id"), nullable=False, unique=True),
        *timestamps(),
    )
    op.create_table(
        "onboarding_cells",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("onboarding_plans.id"), nullable=False),
        sa.Column("column_id", sa.Integer, sa.ForeignKey("onboarding_columns.id"), nullable=False),
        sa.Column("text_value", sa.Text),
        sa.Column("date_value", sa.Date),
        sa.Column("planned_date", sa.Date),
        sa.Column("is_completed", sa.Boolean, nullable=False),
        sa.Column("completed_date", sa.Date),
        sa.Column("version", sa.Integer, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("plan_id", "column_id", name="uq_onboarding_cell"),
        sa.CheckConstraint("(is_completed AND completed_date IS NOT NULL) OR (NOT is_completed AND completed_date IS NULL)", name="ck_onboarding_completion"),
    )
    op.create_index("ix_onboarding_cells_plan_id", "onboarding_cells", ["plan_id"])
    op.create_index("ix_onboarding_cells_column_id", "onboarding_cells", ["column_id"])
    # Seed only known columns, no employee plans and no invented extra fields.
    now = datetime.now(timezone.utc)
    companies = sa.table("companies", sa.column("id", sa.Integer))
    for company_id in op.get_bind().execute(sa.select(companies.c.id)).scalars():
        op.bulk_insert(columns, [
            dict(company_id=company_id, title=title, field_type=kind, sort_order=i,
                 is_archived=False, version=1, created_at=now, updated_at=now)
            for i, (title, kind) in enumerate([
                ("Отдел", "text"), ("Дата начала", "date"), ("Пропуск", "stage"),
                ("NDA", "stage"), ("Экзамен на компетентность", "stage"), ("План обучения", "stage"),
            ])
        ])


def downgrade():
    op.drop_table("onboarding_cells")
    op.drop_table("onboarding_plans")
    op.drop_table("onboarding_columns")
