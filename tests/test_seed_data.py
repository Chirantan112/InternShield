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
        assert first_rule_count == 10  # three fixture rules plus seven defaults


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



def test_seed_migrates_only_the_legacy_default_formatting_regex(app, monkeypatch):
    from scripts.seed_data import LEGACY_FORMATTING_PATTERN, DEFAULT_RULES

    monkeypatch.setenv("ADMIN_EMAIL", "format-admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "BootstrapPassword123")
    with app.app_context():
        formatting = DetectionRule(
            name="Suspicious formatting or language",
            description="Legacy default.",
            pattern=LEGACY_FORMATTING_PATTERN,
            match_type="regex",
            points=5,
            is_active=True,
        )
        custom = DetectionRule(
            name="Administrator custom regex",
            description="Custom rule should remain untouched.",
            pattern=r"\bCUSTOM\s+PATTERN\b",
            match_type="regex",
            points=9,
            is_active=True,
        )
        legacy_placement = DetectionRule(
            name="Unrealistic employment promises",
            description="Legacy default phrase list.",
            pattern="custom administrator phrase, 100% placement, guaranteed job",
            match_type="keyword",
            points=15,
            is_active=True,
        )
        db.session.add_all([formatting, custom, legacy_placement])
        db.session.commit()

        seed()

        saved_formatting = db.session.query(DetectionRule).filter_by(
            name="Suspicious formatting or language"
        ).one()
        saved_custom = db.session.query(DetectionRule).filter_by(
            name="Administrator custom regex"
        ).one()
        expected = next(
            item["pattern"] for item in DEFAULT_RULES
            if item["name"] == "Suspicious formatting or language"
        )
        assert saved_formatting.pattern == expected
        assert saved_formatting.match_type == "regex"
        assert saved_custom.pattern == r"\bCUSTOM\s+PATTERN\b"

        saved_placement = db.session.query(DetectionRule).filter_by(
            name="Unrealistic employment promises"
        ).one()
        assert "100% placement" not in saved_placement.pattern
        assert "custom administrator phrase" in saved_placement.pattern
        assert "guaranteed job" in saved_placement.pattern
