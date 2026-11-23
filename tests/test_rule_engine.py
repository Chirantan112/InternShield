"""Unit tests for deterministic risk scoring."""

from types import SimpleNamespace

import pytest

from internshield.services.rule_engine import InvalidRulePattern, analyze_offer


def rule(name, pattern, points, *, active=True, match_type="keyword"):
    return SimpleNamespace(
        id=1,
        name=name,
        description=f"Explanation for {name}",
        pattern=pattern,
        points=points,
        is_active=active,
        match_type=match_type,
    )


def test_genuine_offer_without_flags_is_low():
    result = analyze_offer(
        "We invite you to interview for a software internship. Visit https://example.com.",
        [rule("Fee", "registration fee", 30)],
    )
    assert result["score"] == 0
    assert result["risk_level"] == "low"
    assert result["flags"] == []


def test_fee_rule_adds_thirty_points_and_explanation():
    result = analyze_offer(
        "Pay a registration fee before your internship begins.",
        [rule("Fee", "registration fee", 30)],
    )
    assert result["score"] == 30
    assert result["risk_level"] == "low"
    assert result["flags"][0]["rule_name"] == "Fee"
    assert result["flags"][0]["explanation"] == "Explanation for Fee"


def test_risk_threshold_changes_from_low_to_medium_at_31():
    rules = [rule("A", "alpha", 30), rule("B", "beta", 1)]
    low = analyze_offer("alpha", rules)
    medium = analyze_offer("alpha beta", rules)
    assert (low["score"], low["risk_level"]) == (30, "low")
    assert (medium["score"], medium["risk_level"]) == (31, "medium")


def test_high_threshold_and_score_cap():
    result = analyze_offer(
        "alpha beta gamma",
        [rule("A", "alpha", 40), rule("B", "beta", 40), rule("C", "gamma", 40)],
    )
    assert result["score"] == 100
    assert result["raw_score"] == 120
    assert result["risk_level"] == "high"
    assert result["score_capped"] is True


def test_rule_contributes_only_once_for_multiple_matching_terms():
    result = analyze_offer(
        "registration fee and security deposit are requested",
        [rule("Fees", "registration fee, security deposit", 30)],
    )
    assert result["score"] == 30
    assert len(result["flags"]) == 1


def test_matching_is_case_insensitive_and_uses_word_boundaries():
    result = analyze_offer(
        "PAY THE REGISTRATION FEE",
        [rule("Fee", "registration fee", 30)],
    )
    no_match = analyze_offer("The payment is optional", [rule("Pay", "pay", 30)])
    assert result["score"] == 30
    assert no_match["score"] == 0


def test_disabled_rule_is_ignored():
    result = analyze_offer(
        "disabled marker",
        [rule("Disabled", "disabled marker", 50, active=False)],
    )
    assert result["score"] == 0


def test_invalid_input_and_rule_points_are_rejected():
    with pytest.raises(ValueError):
        analyze_offer("   ", [])
    with pytest.raises(ValueError):
        analyze_offer("alpha", [rule("Bad", "alpha", 101)])


def test_invalid_regex_is_reported():
    with pytest.raises(InvalidRulePattern):
        analyze_offer("test", [rule("Bad regex", "[", 10, match_type="regex")])


def test_large_offer_text_is_processed_within_three_seconds():
    from time import perf_counter

    text = ("A genuine internship description with project details. " * 900)[:49_900]
    text += " registration fee"
    started = perf_counter()
    result = analyze_offer(
        text,
        [rule("Fee", "registration fee", 30)],
    )
    elapsed = perf_counter() - started
    assert result["score"] == 30
    assert elapsed < 3.0


def test_formatting_regex_detects_repeated_punctuation_and_caps():
    formatting_rule = rule(
        "Formatting",
        r"(?:[!?.,]){3,}|\\b[A-Z]{8,}\\b",
        5,
        match_type="regex",
    )
    repeated = analyze_offer("APPLY NOW!!!", [formatting_rule])
    capitalized = analyze_offer("INTERNSHIP OPPORTUNITY", [formatting_rule])
    assert repeated["score"] == 5
    assert capitalized["score"] == 5
