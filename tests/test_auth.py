"""Authentication and account-creation tests."""

from sqlalchemy import select
from werkzeug.security import check_password_hash

from internshield.extensions import db
from internshield.models import User


def test_public_registration_creates_student_with_hashed_password(client, app):
    response = client.post(
        "/register",
        data={
            "name": "New Student",
            "email": "new@example.com",
            "password": "StrongPassword123",
            "password_confirm": "StrongPassword123",
            "role": "admin",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "new@example.com")
        )
        assert user is not None
        assert user.role == "student"
        assert user.password_hash != "StrongPassword123"
        assert check_password_hash(user.password_hash, "StrongPassword123")


def test_registration_rejects_short_password(client):
    response = client.post(
        "/register",
        data={
            "name": "Short Password",
            "email": "short@example.com",
            "password": "short",
            "password_confirm": "short",
        },
    )
    assert response.status_code == 200
    assert b"at least 10 characters" in response.data


def test_registration_rejects_mismatched_passwords(client):
    response = client.post(
        "/register",
        data={
            "name": "Mismatch",
            "email": "mismatch@example.com",
            "password": "StrongPassword123",
            "password_confirm": "DifferentPassword123",
        },
    )
    assert response.status_code == 200
    assert b"do not match" in response.data


def test_login_rejects_wrong_password(client):
    client.post(
        "/register",
        data={
            "name": "Login Student",
            "email": "login@example.com",
            "password": "StrongPassword123",
            "password_confirm": "StrongPassword123",
        },
    )
    client.post("/logout")
    response = client.post(
        "/login",
        data={"email": "login@example.com", "password": "incorrect"},
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_admin_login_redirects_to_admin_dashboard(admin_client):
    response = admin_client.get("/admin/", follow_redirects=True)
    assert response.status_code == 200
    assert b"InternShield overview" in response.data


def test_logout_ends_session(client, student):
    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been logged out" in response.data
    assert b"Log in to InternShield" in response.data



def test_login_is_rate_limited_after_five_failed_attempts(client):
    for _ in range(5):
        response = client.post(
            "/login",
            data={"email": "nobody@example.com", "password": "incorrect"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "incorrect"},
    )
    assert blocked.status_code == 429
    assert b"Too many login attempts" in blocked.data


def test_unknown_browser_page_returns_html_not_json(client):
    response = client.get("/this-page-does-not-exist", headers={"Accept": "text/html"})
    assert response.status_code == 404
    assert response.mimetype == "text/html"
    assert b"Page not found" in response.data


def test_unknown_json_endpoint_can_request_json_404(client):
    response = client.get(
        "/this-page-does-not-exist",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 404
    assert response.is_json
    assert "error" in response.get_json()



def test_registration_requires_email_otp_before_login(client, app, monkeypatch):
    import internshield.routes.auth as auth_routes

    app.config["EMAIL_VERIFICATION_REQUIRED"] = True
    sent = []
    monkeypatch.setattr(
        auth_routes, "send_verification_email",
        lambda recipient, otp: sent.append((recipient, otp)),
    )

    response = client.post(
        "/register",
        data={
            "name": "Unverified Student",
            "email": "verify@example.com",
            "password": "StrongPassword123",
            "password_confirm": "StrongPassword123",
        },
    )
    assert response.status_code == 302
    assert "/verify-email" in response.headers["Location"]
    assert sent and sent[0][0] == "verify@example.com"

    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "verify@example.com")
        )
        assert user is not None
        assert user.email_verified is False
        assert user.email_verification_otp_hash != sent[0][1]

    login_response = client.post(
        "/login",
        data={"email": "verify@example.com", "password": "StrongPassword123"},
    )
    assert login_response.status_code == 302
    assert "/verify-email" in login_response.headers["Location"]

    verified = client.post(
        "/verify-email",
        data={"email": "verify@example.com", "otp": sent[0][1]},
        follow_redirects=True,
    )
    assert verified.status_code == 200
    assert b"Email verified" in verified.data

    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "verify@example.com")
        )
        assert user.email_verified is True
        assert user.email_verification_otp_hash is None


def test_email_otp_rejects_incorrect_code_and_locks_after_five_attempts(
    client, app, monkeypatch
):
    import internshield.routes.auth as auth_routes

    app.config["EMAIL_VERIFICATION_REQUIRED"] = True
    monkeypatch.setattr(
        auth_routes, "send_verification_email", lambda recipient, otp: None
    )
    client.post(
        "/register",
        data={
            "name": "OTP Attempts",
            "email": "attempts@example.com",
            "password": "StrongPassword123",
            "password_confirm": "StrongPassword123",
        },
    )

    for _ in range(5):
        response = client.post(
            "/verify-email",
            data={"email": "attempts@example.com", "otp": "123456"},
        )
        assert response.status_code == 200
        assert b"Incorrect verification code" in response.data

    blocked = client.post(
        "/verify-email",
        data={"email": "attempts@example.com", "otp": "123456"},
    )
    assert b"Too many incorrect codes" in blocked.data


def test_resend_verification_obeys_cooldown(client, app, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import internshield.routes.auth as auth_routes

    app.config["EMAIL_VERIFICATION_REQUIRED"] = True
    sent = []
    monkeypatch.setattr(
        auth_routes, "send_verification_email",
        lambda recipient, otp: sent.append(otp),
    )
    client.post(
        "/register",
        data={
            "name": "Resend Student",
            "email": "resend@example.com",
            "password": "StrongPassword123",
            "password_confirm": "StrongPassword123",
        },
    )
    assert len(sent) == 1

    cooldown = client.post(
        "/resend-verification",
        data={"email": "resend@example.com"},
        follow_redirects=True,
    )
    assert b"Please wait a minute" in cooldown.data
    assert len(sent) == 1

    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "resend@example.com")
        )
        user.email_verification_sent_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db.session.commit()

    resent = client.post(
        "/resend-verification",
        data={"email": "resend@example.com"},
        follow_redirects=True,
    )
    assert b"new verification code has been sent" in resent.data
    assert len(sent) == 2
