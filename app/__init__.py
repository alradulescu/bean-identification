"""Flask application factory for the Coffee Brewing Assistant."""

import os
from flask import Flask
from .models import db


def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

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
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB max upload
        OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", ""),
    )

    if config is not None:
        app.config.from_mapping(config)

    # Initialise extensions
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Register blueprints
    from .routes import main

    app.register_blueprint(main)

    return app
