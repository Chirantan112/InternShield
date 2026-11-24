"""Database models for InternShield."""

from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index

from .extensions import db


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    """A student or administrator account."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student', 'admin')", name="ck_users_role"),
        Index("ix_users_role_created", "role", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # Existing accounts remain verified during the additive schema migration;
    # public registration explicitly creates new accounts as unverified.
    email_verified = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    email_verification_otp_hash = db.Column(db.String(255))
    email_verification_expires_at = db.Column(db.DateTime(timezone=True))
    email_verification_sent_at = db.Column(db.DateTime(timezone=True))
    email_verification_attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    checks = db.relationship(
        "AnalysisCheck", back_populates="student", cascade="all, delete-orphan"
    )
    reports = db.relationship(
        "ScamReport", back_populates="reporter", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_student(self) -> bool:
        return self.role == "student"


class DetectionRule(db.Model):
    """An administrator-managed rule used by the deterministic rule engine."""

    __tablename__ = "detection_rules"
    __table_args__ = (
        CheckConstraint("points >= 0 AND points <= 100", name="ck_rules_points"),
        CheckConstraint(
            "match_type IN ('keyword', 'regex')", name="ck_rules_match_type"
        ),
        Index("ix_rules_active", "is_active"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=False)
    pattern = db.Column(db.Text, nullable=False)
    match_type = db.Column(db.String(20), nullable=False, default="keyword")
    points = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    flags = db.relationship("CheckFlag", back_populates="rule")


class AnalysisCheck(db.Model):
    """A student's saved offer analysis."""

    __tablename__ = "analysis_checks"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_checks_score"),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high')", name="ck_checks_risk"
        ),
        Index("ix_checks_student_created", "user_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    input_text = db.Column(db.Text, nullable=False)
    source_type = db.Column(db.String(20), nullable=False, default="pasted_text")
    score = db.Column(db.Integer, nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    student = db.relationship("User", back_populates="checks")
    flags = db.relationship(
        "CheckFlag", back_populates="check", cascade="all, delete-orphan"
    )


class CheckFlag(db.Model):
    """A detected warning sign, stored as a snapshot for historical accuracy."""

    __tablename__ = "check_flags"

    id = db.Column(db.Integer, primary_key=True)
    check_id = db.Column(
        db.Integer,
        db.ForeignKey("analysis_checks.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id = db.Column(
        db.Integer, db.ForeignKey("detection_rules.id", ondelete="SET NULL")
    )
    rule_name = db.Column(db.String(120), nullable=False)
    explanation = db.Column(db.String(500), nullable=False)
    points = db.Column(db.Integer, nullable=False)

    check = db.relationship("AnalysisCheck", back_populates="flags")
    rule = db.relationship("DetectionRule", back_populates="flags")


class ScamReport(db.Model):
    """A student-submitted suspicious employer or offer report."""

    __tablename__ = "scam_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_reports_status",
        ),
        Index("ix_reports_status_created", "status", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_name = db.Column(db.String(160), nullable=False)
    offer_details = db.Column(db.Text, nullable=False)
    contact_or_website = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    reporter = db.relationship("User", back_populates="reports")
    reviews = db.relationship(
        "ReportReview", back_populates="report", cascade="all, delete-orphan"
    )


class ReportReview(db.Model):
    """Audit record for each administrator decision on a scam report."""

    __tablename__ = "report_reviews"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer, db.ForeignKey("scam_reports.id", ondelete="CASCADE"), nullable=False
    )
    admin_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL")
    )
    decision = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.String(1000))
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    report = db.relationship("ScamReport", back_populates="reviews")
    admin = db.relationship("User")
