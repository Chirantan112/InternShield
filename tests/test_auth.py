"""Authentication and account-creation tests."""

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from internshield.extensions import db
from internshield.models import User


def test_public_registration_creates_student_and_logs_in(client, app):
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
    assert b"Your student account has been created" in response.data
    assert b"Hello, New Student." in response.data
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "new@example.com"))
        assert user is not None
        assert user.role == "student"
        assert user.email_verified is True
        assert user.password_hash != "StrongPassword123"
        assert check_password_hash(user.password_hash, "StrongPassword123")


def test_registration_rejects_short_password(client):
    response = client.post(
        "/register",
        data={"name": "Short Password", "email": "short@example.com",
              "password": "short", "password_confirm": "short"},
    )
    assert response.status_code == 200
    assert b"at least 10 characters" in response.data


def test_registration_rejects_mismatched_passwords(client):
    response = client.post(
        "/register",
        data={"name": "Mismatch", "email": "mismatch@example.com",
              "password": "StrongPassword123", "password_confirm": "DifferentPassword123"},
    )
    assert response.status_code == 200
    assert b"do not match" in response.data


def test_login_rejects_wrong_password(client):
    client.post(
        "/register",
        data={"name": "Login Student", "email": "login@example.com",
              "password": "StrongPassword123", "password_confirm": "StrongPassword123"},
    )
    client.post("/logout")
    response = client.post(
        "/login", data={"email": "login@example.com", "password": "incorrect"}
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_legacy_unverified_account_can_log_in(client, app):
    with app.app_context():
        user = User(
            name="Legacy Student",
            email="legacy@example.com",
            password_hash=generate_password_hash("StrongPassword123"),
            role="student",
            email_verified=False,
            email_verification_otp_hash="old-otp-hash",
        )
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/login", data={"email": "legacy@example.com", "password": "StrongPassword123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "legacy@example.com"))
        assert user.email_verified is True
        assert user.email_verification_otp_hash is None


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
        response = client.post("/login", data={"email": "nobody@example.com", "password": "incorrect"})
        assert response.status_code == 200
    blocked = client.post("/login", data={"email": "nobody@example.com", "password": "incorrect"})
    assert blocked.status_code == 429
    assert b"Too many login attempts" in blocked.data


def test_unknown_browser_page_returns_html_not_json(client):
    response = client.get("/this-page-does-not-exist", headers={"Accept": "text/html"})
    assert response.status_code == 404
    assert response.mimetype == "text/html"
    assert b"Page not found" in response.data


def test_unknown_json_endpoint_can_request_json_404(client):
    response = client.get("/this-page-does-not-exist", headers={"Accept": "application/json"})
    assert response.status_code == 404
    assert response.is_json
    assert "error" in response.get_json()
