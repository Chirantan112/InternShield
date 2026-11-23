"""Tests for idempotent bootstrap seeding."""

import pytest

from internshield.extensions import db
from internshield.models import DetectionRule, User
from scripts.seed_data import seed


def test_seed_creates_admin_and_default_rules_idempotently(app, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "bootstrap@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "BootstrapPassword123")
    monkeypatch.setenv("ADMIN_NAME", "Bootstrap Admin")
    with app.app_context():
        seed()
        first_rule_count = db.session.query(DetectionRule).count()
        seed()
        assert db.session.query(DetectionRule).count() == first_rule_count
        admin = db.session.query(User).filter_by(email="bootstrap@example.com").one()
        assert admin.role == "admin"
        assert admin.password_hash != "BootstrapPassword123"
        assert first_rule_count == 7


def test_seed_refuses_to_elevate_existing_student(app, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "student@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "BootstrapPassword123")
    with app.app_context():
        db.session.add(
            User(
                name="Existing Student",
                email="student@example.com",
                password_hash="already-hashed",
                role="student",
            )
        )
        db.session.commit()
        with pytest.raises(RuntimeError, match="refusing to silently elevate"):
            seed()
        existing = db.session.query(User).filter_by(email="student@example.com").one()
        assert existing.role == "student"
