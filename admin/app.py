"""
app.py — Flask factory, auth endpoints.
"""

import os
import secrets
from flask import Flask, jsonify, request, session, redirect, url_for, render_template
from routes import register

ADMIN_PASSWORD = os.environ.get("ADMIN_WEB_PASSWORD", "admin123")


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("ADMIN_SECRET_KEY", secrets.token_hex(32))
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    register(app)
    _add_auth_routes(app)
    return app


def _add_auth_routes(app: Flask):
    def need_auth(f):
        from functools import wraps
        @wraps(f)
        def wrap(*a, **kw):
            if not session.get("ok"):
                return (jsonify({"error": "Unauthorized"}), 401) if request.is_json else redirect("/")
            return f(*a, **kw)
        return wrap

    # Inject decorator into all /api/* routes
    for bp in app.blueprints.values():
        for ep in list(app.view_functions.keys()):
            if ep.startswith(bp.name + "."):
                app.view_functions[ep] = need_auth(app.view_functions[ep])

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/login")
    def login():
        if (request.json or {}).get("password") == ADMIN_PASSWORD:
            session["ok"] = True
            return jsonify({"ok": True})
        return jsonify({"error": "Неверный пароль"}), 401

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/me")
    def me():
        return jsonify({"logged_in": bool(session.get("ok"))})


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
