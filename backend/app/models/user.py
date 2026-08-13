"""User and role models."""

from __future__ import annotations

from enum import Enum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class RoleName(str, Enum):
    ADMIN = "admin"
    HR = "hr"
    VIEWER = "viewer"


class AuthSource(str, Enum):
    LOCAL = "local"
    LDAP = "ldap"


class Role(db.Model, TimestampMixin):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)

    users = db.relationship("User", back_populates="role")


class User(UserMixin, db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    full_name = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, default=1)
    auth_source = db.Column(db.String(16), default=AuthSource.LOCAL.value, nullable=False)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)

    role = db.relationship("Role", back_populates="users")
    company = db.relationship("Company")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else RoleName.VIEWER.value

    def has_role(self, *roles: RoleName) -> bool:
        return self.role_name in {role.value for role in roles}

    def can_edit(self) -> bool:
        return self.has_role(RoleName.ADMIN, RoleName.HR)

    def is_admin(self) -> bool:
        return self.has_role(RoleName.ADMIN)

    def record_failed_login(self) -> None:
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            from datetime import timedelta

            self.locked_until = utcnow() + timedelta(minutes=15)

    def reset_failed_login(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None

    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        locked_until = self.locked_until
        now = utcnow()
        if locked_until.tzinfo is None:
            from datetime import timezone

            locked_until = locked_until.replace(tzinfo=timezone.utc)
        return locked_until > now
