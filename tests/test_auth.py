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
            "email": "new@example.test",
            "password": "StrongPassword123",
            "password_confirm": "StrongPassword123",
            "role": "admin",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = db.session.scalar(
            select(User).where(User.email == "new@example.test")
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
            "email": "short@example.test",
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
            "email": "mismatch@example.test",
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
            "email": "login@example.test",
            "password": "StrongPassword123",
            "password_confirm": "StrongPassword123",
        },
    )
    client.post("/logout")
    response = client.post(
        "/login",
        data={"email": "login@example.test", "password": "incorrect"},
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
