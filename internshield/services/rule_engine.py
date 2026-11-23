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
        "raw_score": raw_score,
        "score_capped": raw_score > 100,
        "disclaimer": (
            "This is a preliminary rule-based assessment, not proof of fraud. "
            "Review the offer and verify the employer independently."
        ),
    }
