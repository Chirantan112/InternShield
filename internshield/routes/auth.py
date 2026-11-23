"""Registration, login, and logout routes."""

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import User


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register a student account; public registration cannot create admins."""
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email_input = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not name or len(name) > 100:
            flash("Enter your name (maximum 100 characters).", "danger")
            return render_template("register.html")

        try:
            email = validate_email(
                email_input, check_deliverability=False
            ).normalized.casefold()
        except EmailNotValidError:
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
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="student",
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
def login():
    """Authenticate an existing student or administrator."""
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
            # Keep the response generic to avoid disclosing registered accounts.
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

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
