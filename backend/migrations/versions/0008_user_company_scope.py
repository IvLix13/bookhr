"""Add user company scope and must_change_password flag."""

from alembic import op
import sqlalchemy as sa


revision = "0008_user_company_scope"
down_revision = "0007_import_job_type"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )

    op.execute("UPDATE users SET company_id = 1 WHERE company_id IS NULL")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("company_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_users_company_id",
            "companies",
            ["company_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("fk_users_company_id", type_="foreignkey")
        batch_op.drop_column("must_change_password")
        batch_op.drop_column("company_id")
