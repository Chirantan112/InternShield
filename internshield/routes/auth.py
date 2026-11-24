"""Registration, login, and logout routes."""

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, limiter
from ..models import User


auth_bp = Blueprint("auth", __name__)


def _normalized_email(value: str) -> str | None:
    try:
        return validate_email(value, check_deliverability=False).normalized.casefold()
    except EmailNotValidError:
        return None


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def register():
    """Create a student account and sign the student in immediately."""
    if current_user.is_authenticated:
        destination = "admin.dashboard" if current_user.is_admin else "student.dashboard"
        return redirect(url_for(destination))

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

        min_password_length = 10
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
            flash("An account with that email already exists. Try signing in.", "danger")
            return render_template("register.html")

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="student",
            email_verified=True,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        login_user(user)
        flash("Your student account has been created.", "success")
        return redirect(url_for("student.dashboard"))

    return render_template("register.html")


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

        # Accounts created before OTP removal are also allowed to sign in.
        if not user.email_verified:
            user.email_verified = True
            user.email_verification_otp_hash = None
            user.email_verification_expires_at = None
            user.email_verification_sent_at = None
            user.email_verification_attempts = 0
            db.session.commit()

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
