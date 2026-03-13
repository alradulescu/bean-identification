"""Flask application factory for the Coffee Brewing Assistant."""

import os
import logging
from flask import Flask, request
from sqlalchemy import text
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from .models import db


def _apply_sqlite_schema_fixes(app: Flask) -> None:
    """Patch older SQLite schemas by adding newly introduced nullable columns."""
    db_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    if not db_uri.startswith("sqlite"):
        return

    # Keep this list additive-only to avoid destructive migrations.
    required_columns: dict[str, dict[str, str]] = {
        "coffee_sessions": {
            "producer": "VARCHAR(128)",
            "process": "VARCHAR(64)",
            "decaf_status": "VARCHAR(16)",
            "certifications": "VARCHAR(256)",
            "lot_number": "VARCHAR(64)",
        },
        "brewing_feedback": {
            "adjusted_recipe_json": "TEXT",
        },
    }

    with db.engine.begin() as conn:
        for table_name, columns in required_columns.items():
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            if not rows:
                continue

            existing = {row[1] for row in rows}
            for col_name, col_type in columns.items():
                if col_name in existing:
                    continue
                conn.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN {col_name} {col_type}"
                    )
                )
                app.logger.info(
                    "Applied SQLite schema fix: added %s.%s",
                    table_name,
                    col_name,
                )


def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    logger = logging.getLogger(__name__)

    # Ensure the instance and uploads folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    uploads_dir = os.path.join(app.instance_path, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            f"sqlite:///{os.path.join(app.instance_path, 'coffee.db')}",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=uploads_dir,
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,  # 32 MB max upload
        OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", ""),
    )

    if config is not None:
        app.config.from_mapping(config)

    # Initialise extensions
    db.init_app(app)

    with app.app_context():
        db.create_all()
        _apply_sqlite_schema_fixes(app)

    # Register blueprints
    from .routes import main

    app.register_blueprint(main)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(_exc):
        if not request.path.startswith("/api/"):
            return "Uploaded file is too large", 413
        return (
            {
                "error": (
                    "Uploaded image is too large. Please use an image under 32 MB."
                )
            },
            413,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        if not request.path.startswith("/api/"):
            if isinstance(exc, HTTPException):
                return exc
            raise exc

        # Keep API responses machine-readable for frontend error handling.
        if isinstance(exc, HTTPException):
            return {"error": exc.description or "Request failed"}, exc.code

        logger.exception("Unhandled server error: %s", exc)
        return {"error": "Server failed to process this request"}, 500

    return app
