"""Last published result from the external personal-document checks."""

from app.extensions import db


class PersonalDocumentErrorsSnapshot(db.Model):
    __tablename__ = "personal_document_errors_snapshots"

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    items = db.Column(db.JSON, nullable=False)
    last_success_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_attempt_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_attempt_succeeded = db.Column(db.Boolean, nullable=False)
    attempt_version = db.Column(db.BigInteger, nullable=False)
