"""Company model."""

from __future__ import annotations

import uuid

from app.extensions import db
from app.models.base import TimestampMixin


class Company(db.Model, TimestampMixin):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.Uuid, default=uuid.uuid4, unique=True, nullable=False)
    name = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    onboarding_docx_template = db.Column(db.LargeBinary, nullable=True)
    onboarding_template_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    employments = db.relationship("Employment", back_populates="company")
