"""Tests for SMTP verification email delivery."""

from unittest.mock import MagicMock

import pytest

from internshield.services import email as email_service


def test_gmail_smtp_uses_starttls_and_sends_otp(monkeypatch):
    smtp = MagicMock()
    monkeypatch.setenv("MAIL_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("MAIL_PORT", "587")
    monkeypatch.setenv("MAIL_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "app-password")
    monkeypatch.delenv("MAIL_DEFAULT_SENDER", raising=False)
    monkeypatch.setattr(email_service.smtplib, "SMTP", MagicMock(return_value=smtp))

    email_service.send_verification_email("student@example.com", "123456")

    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("sender@gmail.com", "app-password")
    sent = smtp.send_message.call_args.args[0]
    assert sent["To"] == "student@example.com"
    assert sent["From"] == "sender@gmail.com"
    assert "123456" in sent.get_content()
    assert "10 minutes" in sent.get_content()


def test_smtp_requires_all_credentials(monkeypatch):
    monkeypatch.setenv("MAIL_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("MAIL_USERNAME", "sender@gmail.com")
    monkeypatch.delenv("MAIL_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="SMTP email delivery requires"):
        email_service.send_verification_email("student@example.com", "123456")


def test_smtp_failure_does_not_leak_provider_details(monkeypatch):
    monkeypatch.setenv("MAIL_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("MAIL_PORT", "587")
    monkeypatch.setenv("MAIL_USERNAME", "sender@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "secret-app-password")
    smtp = MagicMock()
    smtp.login.side_effect = email_service.smtplib.SMTPAuthenticationError(535, b"bad credentials")
    monkeypatch.setattr(email_service.smtplib, "SMTP", MagicMock(return_value=smtp))

    with pytest.raises(RuntimeError) as error:
        email_service.send_verification_email("student@example.com", "123456")
    assert "secret-app-password" not in str(error.value)
