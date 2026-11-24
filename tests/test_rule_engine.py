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


def test_formatting_regex_detects_repeated_punctuation_without_flagging_caps():
    formatting_rule = rule(
        "Formatting",
        r"(?:[!?.,]){3,}",
        5,
        match_type="regex",
    )
    repeated = analyze_offer("APPLY NOW!!!", [formatting_rule])
    capitalized = analyze_offer("INTERNSHIP OPPORTUNITY", [formatting_rule])
    assert repeated["score"] == 5
    assert capitalized["score"] == 0
    assert capitalized["flags"] == []


def test_sensitive_identity_and_otp_terms_are_flagged():
    result = analyze_offer(
        "Please share your Aadhaar number and OTP to complete onboarding.",
        [rule("Sensitive information", "aadhaar, otp", 20)],
    )
    assert result["score"] == 20
    assert result["risk_level"] == "low"
    assert result["flags"][0]["rule_name"] == "Sensitive information"


def test_realistic_paid_training_offer_phrases_are_detected():
    from scripts.seed_data import DEFAULT_RULES

    offer = (
        "Today is the final date to apply for the training and internship program. "
        "Only 18 scholarship slots remain. Applicable training fees are required. "
        "Please share your ID number with the counsellor. "
        "The program advertises 100% Placement Assistance. CERTIFICATIONS PROVIDED."
    )
    configured_rules = [
        rule(
            item["name"],
            item["pattern"],
            item["points"],
            match_type=item.get("match_type", "keyword"),
        )
        for item in DEFAULT_RULES
    ]

    result = analyze_offer(offer, configured_rules)

    assert result["score"] == 65
    assert result["risk_level"] == "high"
    detected_names = {flag["rule_name"] for flag in result["flags"]}
    assert "Upfront fees or deposits" in detected_names
    assert "Sensitive personal or financial information" in detected_names
    assert "Urgency or pressure tactics" in detected_names


def test_keyword_pattern_upgrade_preserves_admin_terms_and_is_idempotent():
    from scripts.seed_data import merge_keyword_patterns

    original = "custom administrator phrase, registration fee"
    upgraded = merge_keyword_patterns(
        original,
        "registration fee, applicable training fees, training fees",
    )
    repeated = merge_keyword_patterns(
        upgraded,
        "registration fee, applicable training fees, training fees",
    )

    assert upgraded.startswith(original)
    assert "custom administrator phrase" in upgraded
    assert upgraded.count("applicable training fees") == 1
    assert repeated == upgraded



def test_contextual_training_discount_form_and_placement_prompts_do_not_change_score():
    offer = (
        "Skill development training and internship program. "
        "Use referral code for a 30% discount. Complete the Google Form for onboarding. "
        "We provide placement assistance and career support."
    )
    result = analyze_offer(offer, [])
    titles = {item["title"] for item in result["contextual_warnings"]}
    assert result["score"] == 0
    assert "Training is presented alongside an internship" in titles
    assert "Discount, scholarship, or referral language" in titles
    assert "Application or onboarding form mentioned" in titles
    assert "Placement assistance is not a job guarantee" in titles


def test_contextual_prompts_do_not_treat_discount_or_assistance_as_proof_of_fraud():
    from internshield.services.rule_engine import contextual_warnings
    assert contextual_warnings("A 20% discount is available.") == []
    warnings = contextual_warnings(
        "A software internship with career support and placement assistance."
    )
    assert len(warnings) == 1
    assert "not a job guarantee" in warnings[0]["title"].lower()


def test_contextual_payment_and_affiliation_prompts_are_generic_and_score_independent():
    offer = (
        "Training and internship programme with mandatory registration fees. "
        "Delivered in partnership with an external institution."
    )
    result = analyze_offer(offer, [rule("Fee", "registration fees", 30)])
    titles = {item["title"] for item in result["contextual_warnings"]}
    assert result["score"] == 30
    assert "Payment language in a training or internship offer" in titles
    assert "Third-party affiliation or approval claim" in titles


def test_contextual_prompts_do_not_invent_guarantee_when_placement_is_assisted():
    from internshield.services.rule_engine import contextual_warnings
    warnings = contextual_warnings(
        "Placement assistance is available; no guaranteed placement is promised."
    )
    assert len(warnings) == 1
    assert warnings[0]["title"] == "Placement assistance is not a job guarantee"
    assistance_only = contextual_warnings("We provide 100% placement assistance.")
    assert len(assistance_only) == 1
    assert assistance_only[0]["title"] == "Placement assistance is not a job guarantee"
    guarantee = contextual_warnings("We offer guaranteed placement after training.")
    assert guarantee == []



def test_real_offer_scarcity_wording_detects_singular_scholarship_slot():
    from scripts.seed_data import DEFAULT_RULES

    offer = (
        "Greetings from an organisation. Act fast! ONLY 11 SCHOLARSHIP SLOT LEFT! "
        "Training fees are Applicable. Complete the application form. "
        "The program includes training and internship with 100% placement support."
    )
    urgency = next(item for item in DEFAULT_RULES if item["name"] == "Urgency or pressure tactics")
    configured = rule(
        urgency["name"],
        urgency["pattern"],
        urgency["points"],
        match_type=urgency.get("match_type", "keyword"),
    )
    result = analyze_offer(offer, [configured])
    assert result["score"] == 15
    assert result["flags"][0]["rule_name"] == "Urgency or pressure tactics"



def test_normal_uppercase_headings_do_not_trigger_formatting_flag():
    formatting_rule = rule(
        "Formatting",
        r"(?:[!?.,]){3,}",
        5,
        match_type="regex",
    )
    result = analyze_offer(
        "INTERNSHIP OPPORTUNITY\nAPPLICATION PROCESS\nPLEASE READ THE DETAILS",
        [formatting_rule],
    )
    assert result["score"] == 0
    assert result["flags"] == []



def test_placement_assistance_is_not_scored_as_a_guaranteed_job():
    from scripts.seed_data import DEFAULT_RULES

    configured_rules = [
        rule(
            item["name"],
            item["pattern"],
            item["points"],
            match_type=item.get("match_type", "keyword"),
        )
        for item in DEFAULT_RULES
    ]
    assistance = analyze_offer(
        "We provide 100% placement assistance and career support.",
        configured_rules,
    )
    guarantee = analyze_offer(
        "The program provides guaranteed placement after training.",
        configured_rules,
    )
    assert assistance["score"] == 0
    assert "Unrealistic employment promises" not in {
        flag["rule_name"] for flag in assistance["flags"]
    }
    assert guarantee["score"] == 15
