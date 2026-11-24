"""Transactional email delivery for account verification."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def send_verification_email(recipient: str, otp: str) -> None:
    """Send a one-time verification code through Resend's free transactional API.

    Configure RESEND_API_KEY and MAIL_FROM with a verified sender address.
    The provider's free tier currently includes a limited daily/monthly quota.
    """
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("MAIL_FROM", "").strip()
    if not api_key or not sender:
        raise RuntimeError(
            "Email delivery is not configured. Set RESEND_API_KEY and MAIL_FROM."
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
        # Do not expose provider response bodies, API keys, or recipient details.
        raise RuntimeError("The email provider could not send the message.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("The email provider is temporarily unavailable.") from exc
