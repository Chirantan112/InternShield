"""InternShield application factory."""

import os
from pathlib import Path

import click
from flask import Flask, jsonify
from flask_wtf.csrf import CSRFError

from config import CONFIG_BY_NAME
from .extensions import csrf, db, login_manager


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

    # Keep SQLite databases and uploaded files in the private instance folder.
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        # Import lazily so extensions can be initialized without a model cycle.
        from .models import User

        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create database tables for a fresh local installation."""
        from . import models  # noqa: F401 - ensure all models are registered

        db.create_all()
        click.echo("InternShield database tables created.")

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        return jsonify(
            {
                "error": "The form security token is missing or expired. "
                "Refresh the page and try again."
            }
        ), 400

    @app.errorhandler(413)
    def handle_upload_too_large(_error):
        return jsonify(
            {"error": "The uploaded file is too large. The maximum size is 5 MB."}
        ), 413

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": "The requested page was not found."}), 404

    @app.errorhandler(500)
    def handle_server_error(_error):
        db.session.rollback()
        return jsonify(
            {"error": "An unexpected server error occurred. Please try again."}
        ), 500

    return app
