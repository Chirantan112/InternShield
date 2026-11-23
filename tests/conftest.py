"""Shared pytest fixtures for isolated InternShield tests."""

import pytest
from werkzeug.security import generate_password_hash

from internshield import create_app
from internshield.extensions import db
from internshield.models import DetectionRule, User


@pytest.fixture()
def app(tmp_path):
    application = create_app("testing")
    application.config.update(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        SECRET_KEY="pytest-only-secret",
        WTF_CSRF_ENABLED=False,
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        MAX_ANALYSIS_CHARACTERS=50_000,
        AI_ENABLED=False,
    )
    with application.app_context():
        db.create_all()
        db.session.add_all(
            [
                DetectionRule(
                    name="Fee request",
                    description="Requests money before employment.",
                    pattern="registration fee, security deposit",
                    match_type="keyword",
                    points=30,
                    is_active=True,
                ),
                DetectionRule(
                    name="Sensitive information",
                    description="Requests sensitive information.",
                    pattern="aadhaar, otp",
                    match_type="keyword",
                    points=20,
                    is_active=True,
                ),
                DetectionRule(
                    name="Disabled sample",
                    description="This rule is disabled.",
                    pattern="disabled marker",
                    match_type="keyword",
                    points=50,
                    is_active=False,
                ),
            ]
        )
        db.session.add(
            User(
                name="Test Admin",
                email="admin@example.test",
                password_hash=generate_password_hash("AdminPassword123"),
                role="admin",
                is_active=True,
            )
        )
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def student(client):
    response = client.post(
        "/register",
        data={
            "name": "Test Student",
            "email": "student@example.test",
            "password": "StudentPassword123",
            "password_confirm": "StudentPassword123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    return response


@pytest.fixture()
def admin_client(app):
    client = app.test_client()
    response = client.post(
        "/login",
        data={"email": "admin@example.test", "password": "AdminPassword123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client
