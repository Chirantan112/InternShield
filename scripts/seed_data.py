"""Idempotently create an administrator and the default detection rules.

Set ADMIN_EMAIL, ADMIN_PASSWORD, and ADMIN_NAME in the local environment
before running: python -m scripts.seed_data
No default credentials are embedded in the repository.
"""

import os
import re
import sys

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from internshield import create_app
from internshield.extensions import db
from internshield.models import DetectionRule, User


DEFAULT_RULES = [
    {
        "name": "Upfront fees or deposits",
        "description": "The offer appears to request registration, processing, training, or security fees before employment. Paid training is not automatically fraudulent, but applicants should verify the provider, total cost, refund terms, and whether the opportunity is actually employment.",
        "pattern": "registration fee, processing fee, security deposit, application fee, pay to apply, payment required, refundable deposit, training fee, training fees, applicable training fees, fees are required, program fee, programme fee, course fee, base fee, training charges, paid training",
        "points": 30,
    },
    {
        "name": "Sensitive personal or financial information",
        "description": "The message asks for sensitive identity, banking, card, password, or one-time-password details. Never share passwords, OTPs, or payment-card security details with a recruiter.",
        "pattern": "aadhaar, aadhar, pan card, bank account, account number, otp, one time password, password, debit card, credit card, cvv, id number, identification number, government id, identity proof, id proof",
        "points": 20,
    },
    {
        "name": "Free email sender",
        "description": "The sender appears to use a consumer email provider rather than a verifiable company domain. This alone does not prove fraud.",
        "pattern": "gmail.com, yahoo.com, outlook.com, hotmail.com",
        "points": 15,
    },
    {
        "name": "Urgency or pressure tactics",
        "description": "The offer uses urgency or scarcity language that may pressure applicants into acting without verification.",
        "pattern": "within 24 hours, immediately, last chance, limited seats, act now, urgent response, today only, final date to apply, slots remain, slots left, slot left, scholarship seat, scholarship seats, scholarship slot, scholarship slots, scholarship slot left, batch closes today, act fast, register now",
        "points": 15,
    },
    {
        "name": "Unverifiable company presence",
        "description": "The offer suggests contact is restricted to informal channels or that no official company website is available.",
        "pattern": "no official website, contact only on whatsapp, whatsapp only, website under maintenance, no company address",
        "points": 15,
    },
    {
        "name": "Unrealistic employment promises",
        "description": "The offer contains unusually strong guarantees or compensation promises that should be independently verified.",
        "pattern": "guaranteed job, 100% placement, guaranteed placement, earn lakhs without work, no interview required",
        "points": 15,
    },
    {
        "name": "Suspicious formatting or language",
        "description": "Repeated punctuation or long all-capital words may indicate unprofessional formatting; review context carefully.",
        "pattern": r"(?:[!?.,]){3,}|\b[A-Z]{8,}\b",
        "match_type": "regex",
        "points": 5,
    },
]


def merge_keyword_patterns(existing_pattern: str, default_pattern: str) -> str:
    """Append missing default keywords without deleting administrator terms."""
    existing_terms = [
        term.strip()
        for term in re.split(r"[,;\n]+", existing_pattern or "")
        if term.strip()
    ]
    known_terms = {term.casefold() for term in existing_terms}
    merged_terms = list(existing_terms)

    for term in re.split(r"[,;\n]+", default_pattern or ""):
        candidate = term.strip()
        if candidate and candidate.casefold() not in known_terms:
            merged_terms.append(candidate)
            known_terms.add(candidate.casefold())

    return ", ".join(merged_terms)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set before seeding.")
    return value


def seed() -> None:
    admin_email = required_env("ADMIN_EMAIL").lower()
    admin_password = required_env("ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME", "InternShield Administrator").strip()
    if len(admin_password) < 10:
        raise RuntimeError("ADMIN_PASSWORD must contain at least 10 characters.")

    existing_admin = db.session.query(User).filter_by(email=admin_email).one_or_none()
    if existing_admin is None:
        db.session.add(
            User(
                name=admin_name[:100],
                email=admin_email,
                password_hash=generate_password_hash(admin_password),
                role="admin",
                is_active=True,
            )
        )
        print(f"Created administrator account for {admin_email}.")
    elif existing_admin.role != "admin":
        raise RuntimeError(
            "The configured ADMIN_EMAIL belongs to a non-admin account; "
            "refusing to silently elevate it."
        )
    else:
        print(f"Administrator account {admin_email} already exists; left unchanged.")

    added = 0
    updated = 0
    for item in DEFAULT_RULES:
        existing = db.session.query(DetectionRule).filter_by(name=item["name"]).one_or_none()
        if existing is None:
            rule_data = dict(item)
            match_type = rule_data.pop("match_type", "keyword")
            db.session.add(
                DetectionRule(
                    **rule_data,
                    match_type=match_type,
                    is_active=True,
                )
            )
            added += 1
        elif item.get("match_type", "keyword") == "keyword" and existing.match_type == "keyword":
            merged_pattern = merge_keyword_patterns(existing.pattern, item["pattern"])
            if merged_pattern != existing.pattern:
                existing.pattern = merged_pattern
                updated += 1

    db.session.commit()
    print(f"Seeded {added} new default rule(s); updated {updated} existing keyword rule(s).")


def main() -> None:
    app = create_app()
    with app.app_context():
        from internshield import models  # noqa: F401

        db.create_all()
        seed()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
