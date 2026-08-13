"""Application configuration."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default).lower()).lower() == "true"


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://bookuchet_dev_user:change-me-dev@localhost:5432/bookuchet_dev",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
    UPLOAD_DIR = os.getenv(
        "UPLOAD_DIR",
        str(Path(__file__).resolve().parents[1] / "uploads"),
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_ENABLED = False
    NEXTCLOUD_BASE_URL = os.getenv("NEXTCLOUD_BASE_URL", "")
    NEXTCLOUD_BOT_TOKEN = os.getenv("NEXTCLOUD_BOT_TOKEN", "")

    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "10"))
    PASSWORD_REQUIRE_UPPER = _env_bool("PASSWORD_REQUIRE_UPPER", True)
    PASSWORD_REQUIRE_LOWER = _env_bool("PASSWORD_REQUIRE_LOWER", True)
    PASSWORD_REQUIRE_DIGIT = _env_bool("PASSWORD_REQUIRE_DIGIT", True)
    PASSWORD_REQUIRE_SPECIAL = _env_bool("PASSWORD_REQUIRE_SPECIAL", False)

    LDAP_ENABLED = _env_bool("LDAP_ENABLED", False)
    LDAP_URI = os.getenv("LDAP_URI", "")
    LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
    LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")
    LDAP_USER_BASE_DN = os.getenv("LDAP_USER_BASE_DN", "")
    LDAP_USER_FILTER = os.getenv("LDAP_USER_FILTER", "(sAMAccountName={username})")
    LDAP_USE_TLS = _env_bool("LDAP_USE_TLS", False)
    LDAP_TLS_CA_FILE = os.getenv("LDAP_TLS_CA_FILE", "")
    LDAP_ATTR_USERNAME = os.getenv("LDAP_ATTR_USERNAME", "sAMAccountName")
    LDAP_ATTR_FULL_NAME = os.getenv("LDAP_ATTR_FULL_NAME", "displayName")
    LDAP_DEFAULT_ROLE = os.getenv("LDAP_DEFAULT_ROLE", "viewer")
    LDAP_LOCAL_ADMIN_USERNAME = os.getenv("LDAP_LOCAL_ADMIN_USERNAME", "admin")

    LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "10 per minute")
    NOTIFICATION_MAX_ATTEMPTS = int(os.getenv("NOTIFICATION_MAX_ATTEMPTS", "10"))
    NOTIFICATION_BATCH_SIZE = int(os.getenv("NOTIFICATION_BATCH_SIZE", "100"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    LDAP_ENABLED = False
    RATELIMIT_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
