"""Employee domain: Person, Employment, history."""

from __future__ import annotations

import uuid
from enum import Enum

from app.extensions import db
from app.models.base import TimestampMixin


class EmploymentStatus(str, Enum):
    ACTIVE = "active"
    DISMISSED = "dismissed"


class EducationStatus(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class Person(db.Model, TimestampMixin):
    __tablename__ = "persons"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.Uuid, default=uuid.uuid4, unique=True, nullable=False)
    education_status = db.Column(
        db.String(16),
        default=EducationStatus.UNKNOWN.value,
        nullable=False,
    )

    employments = db.relationship("Employment", back_populates="person")
    name_history = db.relationship("PersonNameHistory", back_populates="person")
    passports = db.relationship("Passport", back_populates="person")
    tenure_awards = db.relationship("TenureAward", back_populates="person")


class Employment(db.Model, TimestampMixin):
    __tablename__ = "employments"

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    status = db.Column(db.String(32), default=EmploymentStatus.ACTIVE.value, nullable=False)
    hire_date = db.Column(db.Date, nullable=False)
    dismissal_date = db.Column(db.Date, nullable=True)
    dismissal_reason = db.Column(db.Text, nullable=True)

    person = db.relationship("Person", back_populates="employments")
    company = db.relationship("Company", back_populates="employments")
    position_history = db.relationship("PositionHistory", back_populates="employment")
    contracts = db.relationship("Contract", back_populates="employment")
    grade_history = db.relationship("EmployeeGradeHistory", back_populates="employment")
    rewards = db.relationship("Reward", back_populates="employment")
    events = db.relationship("Event", back_populates="employment")

    @property
    def is_active(self) -> bool:
        return self.status == EmploymentStatus.ACTIVE.value


class PersonNameHistory(db.Model, TimestampMixin):
    __tablename__ = "person_name_history"

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("persons.id"), nullable=False)
    full_name = db.Column(db.String(256), nullable=False)
    valid_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date, nullable=True)

    person = db.relationship("Person", back_populates="name_history")


class PositionHistory(db.Model, TimestampMixin):
    __tablename__ = "position_history"

    id = db.Column(db.Integer, primary_key=True)
    employment_id = db.Column(db.Integer, db.ForeignKey("employments.id"), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    position_grade_id = db.Column(db.Integer, db.ForeignKey("grade_catalog.id"), nullable=True)
    valid_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date, nullable=True)

    employment = db.relationship("Employment", back_populates="position_history")
    position_grade = db.relationship("GradeCatalog", foreign_keys=[position_grade_id])
