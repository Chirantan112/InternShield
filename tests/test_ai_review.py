"""Tests for the opt-in supplementary AI review service."""

import json
from io import BytesIO

import pytest

from internshield.services.ai_review import AIReviewError, request_ai_review


def test_ai_review_is_disabled_without_configuration():
    with pytest.raises(AIReviewError, match="not configured"):
        request_ai_review("Offer text", {"AI_ENABLED": False})


def test_ai_review_rejects_non_https_remote_endpoint():
    config = {
        "AI_ENABLED": True,
        "AI_API_KEY": "test-key",
        "AI_BASE_URL": "http://provider.example/v1",
        "AI_MODEL": "test-model",
    }
    with pytest.raises(AIReviewError, match="HTTPS"):
        request_ai_review("Offer text", config)


def test_ai_review_parses_supplementary_json_and_bounds_input(monkeypatch):
    response_body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "Verify the employer.",
                            "additional_concerns": ["The sender is unverified."],
                            "verification_steps": ["Check the official company website."],
                        }
                    )
                }
            }
        ]
    }
    captured = {}

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse(json.dumps(response_body).encode("utf-8"))

    monkeypatch.setattr(
        "internshield.services.ai_review.urlopen", fake_urlopen
    )
    result = request_ai_review(
        "X" * 12_000,
        {
            "AI_ENABLED": True,
            "AI_API_KEY": "test-key",
            "AI_BASE_URL": "https://provider.example/v1",
            "AI_MODEL": "test-model",
        },
    )
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["timeout"] == 20
    assert captured["authorization"] == "Bearer test-key"
    assert len(captured["payload"]["messages"][1]["content"]) < 10_100
    assert result["summary"] == "Verify the employer."
    assert result["additional_concerns"] == ["The sender is unverified."]
    assert result["verification_steps"] == ["Check the official company website."]
