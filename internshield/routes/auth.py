"""Registration, email verification, login, and logout routes."""

import secrets
from datetime import datetime, timedelta, timezone

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, limiter
from ..models import User
from ..services.email import send_verification_email


auth_bp = Blueprint("auth", __name__)

OTP_LIFETIME = timedelta(minutes=10)
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
MAX_OTP_ATTEMPTS = 5


def _normalized_email(value: str) -> str | None:
    try:
        return validate_email(value, check_deliverability=False).normalized.casefold()
    except EmailNotValidError:
        return None


def _send_new_otp(user: User) -> None:
    """Persist a fresh OTP hash before asking the provider to deliver the code."""
    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(timezone.utc)
    user.email_verification_otp_hash = generate_password_hash(otp)
    user.email_verification_expires_at = now + OTP_LIFETIME
    user.email_verification_sent_at = now
    user.email_verification_attempts = 0
    db.session.commit()
    send_verification_email(user.email, otp)


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive timestamps and PostgreSQL aware timestamps."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def register():
    """Create a student account; new accounts must verify their email."""
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = _normalized_email(request.form.get("email", "").strip())
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not name or len(name) > 100:
            flash("Enter your name (maximum 100 characters).", "danger")
            return render_template("register.html")
        if not email:
            flash("Enter a valid email address.", "danger")
            return render_template("register.html")

        min_password_length = current_app.config["MIN_PASSWORD_LENGTH"]
        if len(password) < min_password_length:
            flash(
                f"Password must contain at least {min_password_length} characters.",
                "danger",
            )
            return render_template("register.html")
        if password != password_confirm:
            flash("The passwords do not match.", "danger")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Try signing in or verifying it.", "danger")
            return render_template("register.html")

        require_verification = current_app.config.get("EMAIL_VERIFICATION_REQUIRED", True)
        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="student",
            email_verified=not require_verification,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        if not require_verification:
            login_user(user)
            flash("Your student account has been created.", "success")
            return redirect(url_for("student.dashboard"))

        try:
            _send_new_otp(user)
        except RuntimeError:
            current_app.logger.exception("Could not send account verification email.")
            flash(
                "Your account is pending verification, but the email could not be sent. "
                "Please try resending the code later.",
                "warning",
            )
        else:
            flash("We sent a 6-digit verification code to your email address.", "success")
        return redirect(url_for("auth.verify_email", email=email))

    return render_template("register.html")


@auth_bp.route("/verify-email", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def verify_email():
    """Verify ownership of the registered email using a short-lived OTP."""
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))

    email_input = request.form.get("email", "") if request.method == "POST" else request.args.get("email", "")
    email = _normalized_email(email_input.strip())
    if request.method == "GET":
        if not email:
            return redirect(url_for("auth.register"))
        return render_template("verify_email.html", email=email)

    otp = request.form.get("otp", "").strip()
    user = User.query.filter_by(email=email).first() if email else None
    if (
        user is None
        or user.email_verified
        or not user.email_verification_otp_hash
        or not user.email_verification_expires_at
    ):
        flash("That verification request is invalid. Register or request a new code.", "danger")
        return render_template("verify_email.html", email=email or "")

    if user.email_verification_attempts >= MAX_OTP_ATTEMPTS:
        flash("Too many incorrect codes. Request a new verification code.", "danger")
        return render_template("verify_email.html", email=email)

    expires_at = _as_utc(user.email_verification_expires_at)
    if datetime.now(timezone.utc) >= expires_at:
        user.email_verification_otp_hash = None
        user.email_verification_expires_at = None
        db.session.commit()
        flash("That code has expired. Request a new one.", "warning")
        return render_template("verify_email.html", email=email)

    user.email_verification_attempts += 1
    if len(otp) != 6 or not otp.isdigit() or not check_password_hash(
        user.email_verification_otp_hash, otp
    ):
        db.session.commit()
        flash("Incorrect verification code.", "danger")
        return render_template("verify_email.html", email=email)

    user.email_verified = True
    user.email_verification_otp_hash = None
    user.email_verification_expires_at = None
    user.email_verification_sent_at = None
    user.email_verification_attempts = 0
    db.session.commit()
    login_user(user)
    flash("Email verified. Your InternShield account is ready.", "success")
    return redirect(url_for("student.dashboard"))


@auth_bp.route("/resend-verification", methods=["POST"])
@limiter.limit("3 per hour", methods=["POST"])
def resend_verification():
    """Resend an OTP with a per-account cooldown and generic responses."""
    email = _normalized_email(request.form.get("email", "").strip())
    user = User.query.filter_by(email=email).first() if email else None
    if user and not user.email_verified:
        now = datetime.now(timezone.utc)
        sent_at = _as_utc(user.email_verification_sent_at) if user.email_verification_sent_at else None
        if sent_at and now - sent_at < OTP_RESEND_COOLDOWN:
            flash("Please wait a minute before requesting another code.", "warning")
        else:
            try:
                _send_new_otp(user)
            except RuntimeError:
                current_app.logger.exception("Could not resend account verification email.")
                flash("The email could not be sent right now. Please try again later.", "danger")
            else:
                flash("A new verification code has been sent.", "success")
    else:
        # Do not disclose whether an address is registered or already verified.
        flash("If the account needs verification, a new code will be sent.", "info")
    return redirect(url_for("auth.verify_email", email=email or ""))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    """Authenticate an existing student or administrator with throttling."""
    if current_user.is_authenticated:
        destination = "admin.dashboard" if current_user.is_admin else "student.dashboard"
        return redirect(url_for(destination))

    if request.method == "POST":
        email = request.form.get("email", "").strip().casefold()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if (
            user is None
            or not user.is_active
            or not check_password_hash(user.password_hash, password)
        ):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        if not user.is_admin and not user.email_verified:
            flash("Verify your email address before signing in.", "warning")
            return redirect(url_for("auth.verify_email", email=user.email))

        login_user(user, remember=request.form.get("remember") == "on")
        flash("Welcome back.", "success")
        destination = "admin.dashboard" if user.is_admin else "student.dashboard"
        return redirect(url_for(destination))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """End the current session using a CSRF-protected POST request."""
    if current_user.is_authenticated:
        logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
