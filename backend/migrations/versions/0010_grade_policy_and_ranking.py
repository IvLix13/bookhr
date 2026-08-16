"""Add education status and freeze grade tenure policy."""

from alembic import op
import sqlalchemy as sa


revision = "0010_grade_policy_and_ranking"
down_revision = "0009_contract_term_years"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade():
    with op.batch_alter_table("persons", schema=None) as batch_op:
        batch_op.add_column(sa.Column("education_status", sa.String(length=16), nullable=True))

    op.execute(
        sa.text(
            "UPDATE persons SET education_status = "
            "CASE WHEN has_university THEN 'yes' ELSE 'no' END"
        )
    )

    unique_constraints = sa.inspect(op.get_bind()).get_unique_constraints(
        "grade_catalog"
    )
    rank_constraint = next(
        constraint
        for constraint in unique_constraints
        if constraint["column_names"] == ["rank"]
    )
    rank_constraint_name = rank_constraint["name"] or "uq_grade_catalog_rank"

    with op.batch_alter_table(
        "grade_catalog",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(rank_constraint_name, type_="unique")
        batch_op.add_column(
            sa.Column(
                "extra_year_without_university",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table("employee_grade_history", schema=None) as batch_op:
        batch_op.add_column(sa.Column("rank_at_assignment", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rank_started_at", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("required_months", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("education_status_at_rank_entry", sa.String(length=16), nullable=True)
        )

    op.execute(
        sa.text(
            """
            UPDATE employee_grade_history
            SET rank_at_assignment = (
                    SELECT grade_catalog.rank
                    FROM grade_catalog
                    WHERE grade_catalog.id = employee_grade_history.grade_id
                ),
                rank_started_at = assigned_date,
                required_months = CAST(ROUND((
                    SELECT grade_catalog.min_years
                    FROM grade_catalog
                    WHERE grade_catalog.id = employee_grade_history.grade_id
                ) * 12) AS INTEGER),
                education_status_at_rank_entry = (
                    SELECT persons.education_status
                    FROM employments
                    JOIN persons ON persons.id = employments.person_id
                    WHERE employments.id = employee_grade_history.employment_id
                )
            """
        )
    )

    with op.batch_alter_table("persons", schema=None) as batch_op:
        batch_op.alter_column(
            "education_status",
            existing_type=sa.String(length=16),
            nullable=False,
            server_default="unknown",
        )
        batch_op.drop_column("has_university")

    with op.batch_alter_table("employee_grade_history", schema=None) as batch_op:
        batch_op.alter_column("rank_at_assignment", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("rank_started_at", existing_type=sa.Date(), nullable=False)
        batch_op.alter_column("required_months", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column(
            "education_status_at_rank_entry",
            existing_type=sa.String(length=16),
            nullable=False,
        )


def downgrade():
    duplicate_rank = op.get_bind().execute(
        sa.text(
            "SELECT rank FROM grade_catalog GROUP BY rank HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_rank is not None:
        raise RuntimeError("Cannot restore unique grade rank while duplicate ranks exist")

    with op.batch_alter_table("persons", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "has_university",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.execute(
        sa.text(
            "UPDATE persons SET has_university = "
            "CASE WHEN education_status = 'yes' THEN true ELSE false END"
        )
    )

    with op.batch_alter_table("persons", schema=None) as batch_op:
        batch_op.drop_column("education_status")

    with op.batch_alter_table("employee_grade_history", schema=None) as batch_op:
        batch_op.drop_column("education_status_at_rank_entry")
        batch_op.drop_column("required_months")
        batch_op.drop_column("rank_started_at")
        batch_op.drop_column("rank_at_assignment")

    with op.batch_alter_table(
        "grade_catalog",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_column("extra_year_without_university")
        batch_op.create_unique_constraint("uq_grade_catalog_rank", ["rank"])
