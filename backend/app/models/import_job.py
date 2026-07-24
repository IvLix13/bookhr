"""Excel import jobs."""

from __future__ import annotations

from enum import Enum

from app.extensions import db
from app.models.base import TimestampMixin


class ImportStatus(str, Enum):
    UPLOADED = "uploaded"
    VALIDATED = "validated"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class ImportJob(db.Model, TimestampMixin):
    __tablename__ = "import_jobs"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(32), default=ImportStatus.UPLOADED.value, nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    summary = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    company = db.relationship("Company")
    uploaded_by = db.relationship("User")
    rows = db.relationship("ImportRow", back_populates="import_job")


class ImportRow(db.Model):
    __tablename__ = "import_rows"

    id = db.Column(db.Integer, primary_key=True)
    import_job_id = db.Column(db.Integer, db.ForeignKey("import_jobs.id"), nullable=False)
    row_number = db.Column(db.Integer, nullable=False)
    raw_data = db.Column(db.JSON, nullable=False)
    action = db.Column(db.String(32), nullable=True)
    person_uuid = db.Column(db.Uuid, nullable=True)
    errors = db.Column(db.JSON, nullable=True)
    warnings = db.Column(db.JSON, nullable=True)

    import_job = db.relationship("ImportJob", back_populates="rows")
