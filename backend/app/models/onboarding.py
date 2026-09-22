"""Configurable onboarding tables; schema changes are data, never DDL."""

from app.extensions import db
from app.models.base import TimestampMixin


class OnboardingColumn(db.Model, TimestampMixin):
    __tablename__ = "onboarding_columns"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    title = db.Column(db.String(256), nullable=False)
    field_type = db.Column(db.String(16), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (db.CheckConstraint("field_type IN ('text', 'date', 'stage', 'checkbox')", name="ck_onboarding_column_type"),)


class OnboardingPlan(db.Model, TimestampMixin):
    __tablename__ = "onboarding_plans"
    id = db.Column(db.Integer, primary_key=True)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=False, unique=True)
    employment = db.relationship("Employment")
    cells = db.relationship("OnboardingCell", back_populates="plan")


class OnboardingCell(db.Model, TimestampMixin):
    __tablename__ = "onboarding_cells"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("onboarding_plans.id"), nullable=False, index=True)
    column_id = db.Column(db.Integer, db.ForeignKey("onboarding_columns.id"), nullable=False, index=True)
    text_value = db.Column(db.Text)
    date_value = db.Column(db.Date)
    planned_date = db.Column(db.Date)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    is_not_required = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    completed_date = db.Column(db.Date)
    version = db.Column(db.Integer, nullable=False, default=1)
    plan = db.relationship("OnboardingPlan", back_populates="cells")
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        db.UniqueConstraint("plan_id", "column_id", name="uq_onboarding_cell"),
        db.CheckConstraint("is_completed OR completed_date IS NULL", name="ck_onboarding_completion"),
        db.CheckConstraint("NOT (is_completed AND is_not_required)", name="ck_onboarding_not_required"),
    )
