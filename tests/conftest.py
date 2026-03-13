"""Pytest fixtures and configuration for the test suite."""

import io
import pytest
from PIL import Image

from app import create_app
from app.models import db as _db


@pytest.fixture(scope="session")
def app():
    """Create a test application with an in-memory SQLite database."""
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": "/tmp/bean_test_uploads",
            "OPENAI_API_KEY": "",  # No real API calls in tests
            "SECRET_KEY": "test-secret",
        }
    )
    import os
    os.makedirs("/tmp/bean_test_uploads", exist_ok=True)

    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """Provide a database session that is rolled back after each test."""
    with app.app_context():
        yield _db
        _db.session.rollback()


@pytest.fixture
def sample_image_bytes():
    """Return raw JPEG bytes of a tiny 10x10 white image."""
    img = Image.new("RGB", (10, 10), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


@pytest.fixture
def sample_image_file(sample_image_bytes):
    """Return a BytesIO-backed file-like object for multipart uploads."""
    return io.BytesIO(sample_image_bytes)
