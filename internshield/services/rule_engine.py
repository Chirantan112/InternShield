"""Explainable, deterministic offer-risk scoring engine."""

import re
from collections.abc import Iterable
from typing import Any


MAX_RULE_PATTERN_LENGTH = 1000


class InvalidRulePattern(ValueError):
    """Raised when an administrator-supplied rule pattern is invalid."""


def _keyword_matches(text: str, pattern: str) -> list[str]:
    """Return configured keywords/phrases found as whole terms in the text.

    A keyword rule accepts comma-, semicolon-, or newline-separated terms.
    Matching is case-insensitive and avoids matching a short term inside a
    different word (for example, 'pay' inside 'payment' is intentionally not
    treated as a match unless the configured term itself is 'payment').
    """
    terms = [
        term.strip()
        for term in re.split(r"[,;\n]+", pattern)
        if term.strip()
    ]
    matches = []
    for term in terms:
        expression = rf"(?<!\w){re.escape(term)}(?!\w)"
        if re.search(expression, text, flags=re.IGNORECASE):
            matches.append(term)
    return matches


def _regex_matches(text: str, pattern: str) -> list[str]:
    """Return the matched text for a validated regular-expression rule."""
    if len(pattern) > MAX_RULE_PATTERN_LENGTH:
        raise InvalidRulePattern("Rule patterns cannot exceed 1000 characters.")
    try:
        compiled = re.compile(pattern, flags=re.IGNORECASE)
    except re.error as exc:
        raise InvalidRulePattern(f"Invalid regular expression: {exc}") from exc

    match = compiled.search(text)
    return [match.group(0)] if match else []


def _risk_level(score: int) -> str:
    """Map a capped score to the project's documented risk bands."""
    if score <= 30:
        return "low"
    if score <= 60:
        return "medium"
    return "high"




_CONTEXT_PATTERNS = {
    "training": r"\b(?:training|skill development|course|bootcamp|certification programme|certification program)\b",
    "internship": r"\b(?:internship|intern|apprenticeship|trainee role)\b",
    "discount": r"\b(?:discount|scholarship|promo(?:tional)? code|coupon|referral code|limited.time offer)\b",
    "payment": r"\b(?:fee|fees|payment|pay|deposit|charges|tuition|registration amount)\b",
    "external_form": r"(?:forms\.gle|docs\.google\.com/forms|typeform\.com|jotform\.com|formstack\.com|\bgoogle form\b|\bapplication form\b|\bonboarding form\b)",
    "placement_assistance": r"\bplacement assistance\b|\bcareer support\b|\bplacement support\b",
    "placement_guarantee": r"\b(?:guaranteed? placement|100\s*%\s*placement|assured placement|job guarantee)\b",
    "affiliation": r"\b(?:in association with|associated with|in partnership with|partnered with|affiliated with|certified by|recognised by|recognized by|approved by)\b",
}


def contextual_warnings(text: str) -> list[dict[str, str]]:
    """Return generic verification prompts without changing the risk score."""
    found = {
        name: bool(re.search(pattern, text, flags=re.IGNORECASE))
        for name, pattern in _CONTEXT_PATTERNS.items()
    }
    warnings: list[dict[str, str]] = []

    if found["training"] and found["internship"]:
        warnings.append({
            "title": "Training is presented alongside an internship",
            "explanation": (
                "Check whether this is a genuine work-based internship or a paid "
                "training/certification course, and request written details of duties, "
                "supervision, duration, and any charges."
            ),
        })
    if found["discount"] and (found["training"] or found["internship"]):
        warnings.append({
            "title": "Discount, scholarship, or referral language",
            "explanation": (
                "Ask for the complete fee schedule, refund terms, and eligibility "
                "conditions in writing. A discount or referral code alone does not "
                "mean the offer is fraudulent."
            ),
        })
    if found["payment"] and (found["training"] or found["internship"]):
        warnings.append({
            "title": "Payment language in a training or internship offer",
            "explanation": (
                "Confirm whether payment is mandatory, who receives it, what it covers, "
                "and whether a refund policy exists. Do not pay to secure a job without "
                "independently verifying the employer and role."
            ),
        })
    if found["external_form"]:
        warnings.append({
            "title": "Application or onboarding form mentioned",
            "explanation": (
                "Verify the form's owner and destination through the organisation's "
                "official website or a known contact. Do not submit passwords, OTPs, "
                "bank credentials, or unnecessary identity documents."
            ),
        })
    if found["placement_assistance"] and not found["placement_guarantee"]:
        warnings.append({
            "title": "Placement assistance is not a job guarantee",
            "explanation": (
                "Treat assistance or career-support wording as a service claim, not a "
                "promise of employment. Ask what support is actually provided and "
                "whether outcomes are documented."
            ),
        })
    if found["affiliation"]:
        warnings.append({
            "title": "Third-party affiliation or approval claim",
            "explanation": (
                "Verify the claimed relationship directly with the named institution, "
                "company, or accrediting body using its official contact channels."
            ),
        })
    return warnings

def analyze_offer(text: str, rules: Iterable[Any]) -> dict[str, Any]:
    """Analyze offer text using active rules and return an explainable result.

    Each rule contributes at most once, even if several configured terms from
    that rule appear in the offer. The final score is capped at 100. A risk
    label is a preliminary indicator, not a factual determination of fraud.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Offer text cannot be empty.")

    detected_flags: list[dict[str, Any]] = []
    raw_score = 0

    for rule in rules:
        if not getattr(rule, "is_active", True):
            continue

        rule_name = str(getattr(rule, "name", "Unnamed rule"))
        explanation = str(getattr(rule, "description", "A warning sign was detected."))
        pattern = str(getattr(rule, "pattern", ""))
        match_type = str(getattr(rule, "match_type", "keyword")).lower()
        points = int(getattr(rule, "points", 0))

        if points < 0 or points > 100:
            raise ValueError(f"Rule '{rule_name}' has an invalid point value.")

        if match_type == "keyword":
            matches = _keyword_matches(text, pattern)
        elif match_type == "regex":
            matches = _regex_matches(text, pattern)
        else:
            raise InvalidRulePattern(
                f"Rule '{rule_name}' uses unsupported match type '{match_type}'."
            )

        if matches:
            raw_score += points
            detected_flags.append(
                {
                    "rule_id": getattr(rule, "id", None),
                    "rule_name": rule_name,
                    "explanation": explanation,
                    "points": points,
                    "matches": matches,
                }
            )

    score = min(raw_score, 100)
    return {
        "score": score,
        "risk_level": _risk_level(score),
        "flags": detected_flags,
        "contextual_warnings": contextual_warnings(text),
        "raw_score": raw_score,
        "score_capped": raw_score > 100,
        "disclaimer": (
            "This is a preliminary rule-based assessment, not proof of fraud. "
            "Review the offer and verify the employer independently."
        ),
    }
