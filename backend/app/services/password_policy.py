"""Password validation rules."""

from __future__ import annotations

import re

from flask import current_app


def validate_password(password: str, username: str) -> None:
    min_length = int(current_app.config.get("PASSWORD_MIN_LENGTH", 10))
    if len(password) < min_length:
        raise ValueError(f"password must be at least {min_length} characters")

    if password.lower() == username.lower():
        raise ValueError("password must not match username")

    if current_app.config.get("PASSWORD_REQUIRE_UPPER", True) and not re.search(r"[A-Z]", password):
        raise ValueError("password must contain an uppercase letter")

    if current_app.config.get("PASSWORD_REQUIRE_LOWER", True) and not re.search(r"[a-z]", password):
        raise ValueError("password must contain a lowercase letter")

    if current_app.config.get("PASSWORD_REQUIRE_DIGIT", True) and not re.search(r"\d", password):
        raise ValueError("password must contain a digit")

    if current_app.config.get("PASSWORD_REQUIRE_SPECIAL", False) and not re.search(
        r"[^A-Za-z0-9]", password
    ):
        raise ValueError("password must contain a special character")
