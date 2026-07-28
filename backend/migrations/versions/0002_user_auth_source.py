"""Add auth_source and nullable password_hash to users."""

from alembic import op
import sqlalchemy as sa


revision = "0002_user_auth_source"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(length=256), nullable=True)
        batch_op.add_column(
            sa.Column(
                "auth_source",
                sa.String(length=16),
                nullable=False,
                server_default="local",
            )
        )


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("auth_source")
        batch_op.alter_column("password_hash", existing_type=sa.String(length=256), nullable=False)
