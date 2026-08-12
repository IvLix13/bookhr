import pytest

from app.services.password_policy import validate_password


def test_validate_password_accepts_strong_password(app):
    with app.app_context():
        validate_password("StrongPass1", "otheruser")


def test_validate_password_rejects_short_password(app):
    with app.app_context():
        with pytest.raises(ValueError, match="at least"):
            validate_password("Short1", "otheruser")


def test_validate_password_rejects_username_match(app):
    with app.app_context():
        with pytest.raises(ValueError, match="must not match username"):
            validate_password("Testuser12", "testuser12")
