"""Global API error handlers."""

from __future__ import annotations

import traceback

from flask import Flask, request
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from app.api.helpers import api_response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        messages = exc.messages
        if isinstance(messages, dict):
            parts = []
            for field, field_errors in messages.items():
                if isinstance(field_errors, (list, tuple)):
                    parts.append(f"{field}: {', '.join(str(item) for item in field_errors)}")
                else:
                    parts.append(f"{field}: {field_errors}")
            message = "; ".join(parts) if parts else "Validation error"
        else:
            message = str(messages)
        return api_response(message=message, status=400)

    @app.errorhandler(ValueError)
    def handle_value_error(exc: ValueError):
        return api_response(message=str(exc) or "Invalid value", status=400)

    @app.errorhandler(KeyError)
    def handle_key_error(exc: KeyError):
        field = exc.args[0] if exc.args else "field"
        return api_response(message=f"Missing required field: {field}", status=400)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_exc: RequestEntityTooLarge):
        return api_response(message="Request entity too large", status=413)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        if request.path.startswith("/api/"):
            return api_response(message=exc.description or exc.name, status=exc.code or 500)
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.error(
            "Unhandled exception on %s %s: %s\n%s",
            request.method,
            request.path,
            exc,
            traceback.format_exc(),
        )
        if request.path.startswith("/api/"):
            return api_response(message="Internal server error", status=500)
        raise exc
