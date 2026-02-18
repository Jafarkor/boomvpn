"""routes/__init__.py — регистрирует все blueprints."""

from .stats import bp as stats_bp
from .users import bp as users_bp
from .payments import bp as payments_bp
from .broadcast import bp as broadcast_bp


def register(app):
    for blueprint in (stats_bp, users_bp, payments_bp, broadcast_bp):
        app.register_blueprint(blueprint, url_prefix="/api")
