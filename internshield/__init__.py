"""InternShield application factory."""

import os
from pathlib import Path

import click
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_limiter.errors import RateLimitExceeded
from flask_wtf.csrf import CSRFError

from config import CONFIG_BY_NAME
from .extensions import csrf, db, limiter, login_manager


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure an InternShield application instance."""
    selected_config = config_name or os.getenv("FLASK_CONFIG", "development")
    config_class = CONFIG_BY_NAME.get(selected_config)
    if config_class is None:
        raise ValueError(
            f"Unknown FLASK_CONFIG '{selected_config}'. "
            f"Choose one of: {', '.join(sorted(CONFIG_BY_NAME))}."
        )

    if selected_config == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set when running in production.")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from .routes.auth import auth_bp
    from .routes.student import student_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def home():
        """Send visitors to the login page or their role-specific dashboard."""
        if not login_manager:
            return redirect(url_for("auth.login"))
        from flask_login import current_user

        if current_user.is_authenticated:
            destination = "admin.dashboard" if current_user.is_admin else "student.dashboard"
            return redirect(url_for(destination))
        return redirect(url_for("auth.login"))

    @login_manager.user_loader
    def load_user(user_id: str):
        from .models import User

        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create database tables for a fresh local installation."""
        from . import models  # noqa: F401

        db.create_all()
        click.echo("InternShield database tables created.")

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        message = (
            "The form security token is missing or expired. "
            "Refresh the page and try again."
        )
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"error": message}), 400
        return render_template("errors/error.html", code=400, message=message), 400

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(_error: RateLimitExceeded):
        message = "Too many login attempts. Wait a minute before trying again."
        return render_template("errors/error.html", code=429, message=message), 429

    @app.errorhandler(413)
    def handle_upload_too_large(_error):
        message = "The uploaded file is too large. The maximum size is 5 MB."
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"error": message}), 413
        return render_template("errors/error.html", code=413, message=message), 413

    @app.errorhandler(404)
    def handle_not_found(_error):
        message = "The page you requested could not be found."
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"error": message}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def handle_server_error(_error):
        db.session.rollback()
        message = "An unexpected server error occurred. Please try again."
        if request.accept_mimetypes.best == "application/json":
            return jsonify({"error": message}), 500
        return render_template("errors/error.html", code=500, message=message), 500

    return app
