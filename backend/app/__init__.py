"""Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from app.config import config_by_name
from app.extensions import db, login_manager, migrate


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.getenv("APP_ENV", "development")

    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="",
    )
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.models import User  # noqa: F401 — register models

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    login_manager.login_view = None

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    from app.api import register_blueprints

    register_blueprints(app)
    register_cli(app)
    register_frontend_routes(app)

    return app


def register_cli(app: Flask) -> None:
    from app.cli import register_commands

    register_commands(app)


def register_frontend_routes(app: Flask) -> None:
    static_dir = Path(app.static_folder or "static")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path: str):
        if path.startswith("api/"):
            return {"error": "Not found"}, 404
        if path and (static_dir / path).is_file():
            return send_from_directory(static_dir, path)
        index = static_dir / "index.html"
        if index.is_file():
            return send_from_directory(static_dir, "index.html")
        return {
            "message": "Bookuchet API",
            "hint": "Build frontend with scripts/build.sh",
        }, 200
