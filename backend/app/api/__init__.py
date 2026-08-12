"""API blueprint registration."""

from flask import Blueprint

from app.api import attention, auth, employees, events, import_api, modules, notifications, rewards, search, stats, users


def register_blueprints(app):
    api = Blueprint("api", __name__, url_prefix="/api")

    auth.register_routes(api)
    employees.register_routes(api)
    events.register_routes(api)
    modules.register_routes(api)
    rewards.register_routes(api)
    import_api.register_routes(api)
    notifications.register_routes(api)
    stats.register_routes(api)
    attention.register_routes(api)
    search.register_routes(api)
    users.register_routes(api)

    app.register_blueprint(api)
