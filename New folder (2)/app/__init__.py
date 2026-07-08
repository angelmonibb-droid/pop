from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import build_config
from . import db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(build_config())
    if test_config:
        app.config.update(test_config)

    if app.config["TRUST_PROXY"]:
        # Enable only when exactly one trusted reverse proxy is in front of the app.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    from . import admin, auth, game

    app.register_blueprint(auth.bp)
    app.register_blueprint(game.bp)
    app.register_blueprint(admin.bp)
    db.init_app(app)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        try:
            db.get_db().execute("SELECT 1").fetchone()
        except Exception:
            return jsonify(status="unhealthy"), 503
        return jsonify(status="ok")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify(error="مسیر درخواستی پیدا نشد."), 404
        return render_template("index.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="حجم درخواست بیش از حد مجاز است."), 413

    return app
