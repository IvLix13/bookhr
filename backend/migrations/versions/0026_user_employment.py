"""Bind calendar viewers to local employment."""
from alembic import op
import sqlalchemy as sa
revision = "0026_user_employment"
down_revision = "0025_staff_directory_fields"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("employment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_users_employment", "employments", ["employment_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_users_employment_id", ["employment_id"])

def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_employment_id")
        batch.drop_constraint("fk_users_employment", type_="foreignkey")
        batch.drop_column("employment_id")
