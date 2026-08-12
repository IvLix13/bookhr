"""Replace grade_catalog.min_months with min_years."""

from alembic import op
import sqlalchemy as sa


revision = "0006_grade_min_years"
down_revision = "0005_import_row_result"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "grade_catalog",
        sa.Column("min_years", sa.Numeric(5, 2), nullable=True),
    )
    op.execute("UPDATE grade_catalog SET min_years = min_months / 12.0")
    op.alter_column("grade_catalog", "min_years", nullable=False)
    op.drop_column("grade_catalog", "min_months")


def downgrade():
    op.add_column(
        "grade_catalog",
        sa.Column("min_months", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE grade_catalog SET min_months = CAST(ROUND(min_years * 12) AS INTEGER)"
    )
    op.alter_column("grade_catalog", "min_months", nullable=False)
    op.drop_column("grade_catalog", "min_years")
