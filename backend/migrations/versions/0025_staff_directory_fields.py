"""External staff directory identity, placement and request cooldown."""
from alembic import op
import sqlalchemy as sa

revision = "0025_staff_directory_fields"
down_revision = "0024_onboarding_shared_mapping"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("persons") as batch:
        batch.add_column(sa.Column("cardnumber", sa.String(128), nullable=True))
        batch.add_column(sa.Column("fio_short", sa.String(256), nullable=True))
        batch.add_column(sa.Column("staff_directory_checked_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint("uq_persons_cardnumber", ["cardnumber"])
    with op.batch_alter_table("employments") as batch:
        batch.add_column(sa.Column("formal_department_short_name", sa.String(256), nullable=True))
        batch.add_column(sa.Column("formal_department_name", sa.Text(), nullable=True))
    with op.batch_alter_table("position_history") as batch:
        batch.add_column(sa.Column("short_title", sa.String(256), nullable=True))
    op.create_table(
        "staff_directory_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("staff_directory_state")
    with op.batch_alter_table("position_history") as batch:
        batch.drop_column("short_title")
    with op.batch_alter_table("employments") as batch:
        batch.drop_column("formal_department_name")
        batch.drop_column("formal_department_short_name")
    with op.batch_alter_table("persons") as batch:
        batch.drop_constraint("uq_persons_cardnumber", type_="unique")
        batch.drop_column("staff_directory_checked_at")
        batch.drop_column("fio_short")
        batch.drop_column("cardnumber")
