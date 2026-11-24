"""Transactional email delivery for account verification."""

import json
import os
import smtplib
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _send_with_smtp(recipient: str, otp: str) -> None:
    host = os.getenv("MAIL_SERVER", "").strip()
    username = os.getenv("MAIL_USERNAME", "").strip()
    password = os.getenv("MAIL_PASSWORD", "")
    if not all((host, username, password)):
        raise RuntimeError(
            "SMTP email delivery requires MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD."
        )

    port = int(os.getenv("MAIL_PORT", "587"))
    sender = os.getenv("MAIL_DEFAULT_SENDER", "").strip() or username
    message = EmailMessage()
    message["Subject"] = "Your InternShield verification code"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Your InternShield verification code is {otp}. "
        "It expires in 10 minutes. If you did not create this account, "
        "you can ignore this email."
    )

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(username, password)
                server.send_message(message)
    except (smtplib.SMTPException, OSError, TimeoutError, ValueError) as exc:
        raise RuntimeError("The SMTP email provider could not send the message.") from exc


def _send_with_resend(recipient: str, otp: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("MAIL_FROM", "").strip()
    if not api_key or not sender:
        raise RuntimeError(
            "Email delivery is not configured. Set SMTP settings or RESEND_API_KEY and MAIL_FROM."
        )

    payload = {
        "from": sender,
        "to": [recipient],
        "subject": "Your InternShield verification code",
        "text": (
            f"Your InternShield verification code is {otp}. "
            "It expires in 10 minutes. If you did not create this account, "
            "you can ignore this email."
        ),
    }
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            if response.status not in (200, 201, 202):
                raise RuntimeError("The email provider rejected the message.")
    except HTTPError as exc:
        raise RuntimeError("The email provider could not send the message.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("The email provider is temporarily unavailable.") from exc


def send_verification_email(recipient: str, otp: str) -> None:
    """Prefer SMTP when configured; otherwise use the existing Resend integration."""
    if os.getenv("MAIL_SERVER", "").strip():
        _send_with_smtp(recipient, otp)
    else:
        _send_with_resend(recipient, otp)
