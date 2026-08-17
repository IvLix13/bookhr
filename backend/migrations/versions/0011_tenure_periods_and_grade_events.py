"""Move tenure awards to person scope and support employment periods."""

from alembic import op
import sqlalchemy as sa


revision = "0011_tenure_periods_and_grade_events"
down_revision = "0010_grade_policy_and_ranking"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def _employment_milestone_unique_name(bind) -> str:
    unique_constraints = sa.inspect(bind).get_unique_constraints("tenure_awards")
    milestone_constraint = next(
        constraint
        for constraint in unique_constraints
        if constraint["column_names"] == ["employment_id", "milestone_years"]
    )
    return milestone_constraint["name"] or "uq_tenure_milestone"


def _employment_foreign_key_name(bind) -> str | None:
    foreign_keys = sa.inspect(bind).get_foreign_keys("tenure_awards")
    for foreign_key in foreign_keys:
        if foreign_key["constrained_columns"] == ["employment_id"]:
            return foreign_key["name"]
    return None


def upgrade():
    with op.batch_alter_table("tenure_awards", schema=None) as batch_op:
        batch_op.add_column(sa.Column("person_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("company_id", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE tenure_awards
            SET person_id = (
                SELECT person_id FROM employments WHERE employments.id = tenure_awards.employment_id
            ),
            company_id = (
                SELECT company_id FROM employments WHERE employments.id = tenure_awards.employment_id
            )
            """
        )
    )

    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            """
            SELECT person_id, company_id, milestone_years, MIN(id) AS keep_id
            FROM tenure_awards
            GROUP BY person_id, company_id, milestone_years
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for row in duplicates:
        bind.execute(
            sa.text(
                """
                DELETE FROM tenure_awards
                WHERE person_id = :person_id
                  AND company_id = :company_id
                  AND milestone_years = :milestone_years
                  AND id != :keep_id
                """
            ),
            {
                "person_id": row.person_id,
                "company_id": row.company_id,
                "milestone_years": row.milestone_years,
                "keep_id": row.keep_id,
            },
        )

    unique_name = _employment_milestone_unique_name(bind)
    employment_fk_name = _employment_foreign_key_name(bind)
    with op.batch_alter_table(
        "tenure_awards",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.alter_column("person_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("company_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_tenure_awards_person_id",
            "persons",
            ["person_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_tenure_awards_company_id",
            "companies",
            ["company_id"],
            ["id"],
        )
        batch_op.drop_constraint(unique_name, type_="unique")
        batch_op.create_unique_constraint(
            "uq_tenure_person_milestone",
            ["person_id", "company_id", "milestone_years"],
        )
        if employment_fk_name:
            batch_op.drop_constraint(employment_fk_name, type_="foreignkey")
        batch_op.drop_column("employment_id")


def downgrade():
    with op.batch_alter_table("tenure_awards", schema=None) as batch_op:
        batch_op.add_column(sa.Column("employment_id", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE tenure_awards
            SET employment_id = (
                SELECT id
                FROM employments
                WHERE employments.person_id = tenure_awards.person_id
                  AND employments.company_id = tenure_awards.company_id
                ORDER BY
                    CASE WHEN employments.status = 'active' THEN 0 ELSE 1 END,
                    employments.hire_date DESC,
                    employments.id DESC
                LIMIT 1
            )
            """
        )
    )

    with op.batch_alter_table(
        "tenure_awards",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.alter_column("employment_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_tenure_awards_employment_id",
            "employments",
            ["employment_id"],
            ["id"],
        )
        batch_op.drop_constraint("uq_tenure_person_milestone", type_="unique")
        batch_op.create_unique_constraint(
            "uq_tenure_milestone",
            ["employment_id", "milestone_years"],
        )
        batch_op.drop_constraint("fk_tenure_awards_company_id", type_="foreignkey")
        batch_op.drop_constraint("fk_tenure_awards_person_id", type_="foreignkey")
        batch_op.drop_column("company_id")
        batch_op.drop_column("person_id")
