"""Add import_type to import_jobs."""

from alembic import op
import sqlalchemy as sa


revision = "0007_import_job_type"
down_revision = "0006_grade_min_years"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "import_jobs",
        sa.Column("import_type", sa.String(length=32), nullable=True),
    )
    op.execute("UPDATE import_jobs SET import_type = 'employees' WHERE import_type IS NULL")
    op.alter_column("import_jobs", "import_type", nullable=False)


def downgrade():
    op.drop_column("import_jobs", "import_type")
