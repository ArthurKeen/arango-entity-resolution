"""
Unit tests for LLMMatchVerifier.

LLM calls are mocked — no API key or network required.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch


RECORD_A = {"name": "Acme Corp", "city": "Boston", "state": "MA"}
RECORD_B = {"name": "Acme Corporation", "city": "Boston", "state": "Massachusetts"}
FIELD_SCORES = {
    "name": {"score": 0.84, "method": "jaro_winkler"},
    "city": {"score": 1.0, "method": "exact"},
    "state": {"score": 0.72, "method": "jaro_winkler"},
}


class TestLLMMatchVerifier:
    def _verifier(self, **kwargs):
        from entity_resolution.reasoning.llm_verifier import LLMMatchVerifier
        return LLMMatchVerifier(model="test/model", api_key="test-key", **kwargs)

    def test_needs_verification_in_range(self):
        v = self._verifier(low_threshold=0.55, high_threshold=0.80)
        assert v.needs_verification(0.70) is True

    def test_needs_verification_above_range(self):
        v = self._verifier(low_threshold=0.55, high_threshold=0.80)
        assert v.needs_verification(0.85) is False

    def test_needs_verification_below_range(self):
        v = self._verifier(low_threshold=0.55, high_threshold=0.80)
        assert v.needs_verification(0.40) is False

    def test_fast_path_high_score_no_llm(self):
        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.95, field_scores=FIELD_SCORES)
        assert result["decision"] == "match"
        assert result["llm_called"] is False

    def test_fast_path_low_score_no_llm(self):
        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.30, field_scores=FIELD_SCORES)
        assert result["decision"] == "no_match"
        assert result["llm_called"] is False

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_llm_called_for_uncertain_score(self, mock_litellm):
        llm_response = MagicMock()
        llm_response.choices[0].message.content = json.dumps({
            "decision": "match",
            "confidence": 0.88,
            "reasoning": "Abbreviation difference only.",
        })
        mock_litellm.completion.return_value = llm_response

        v = self._verifier(low_threshold=0.55, high_threshold=0.80)
        result = v.verify(RECORD_A, RECORD_B, score=0.70, field_scores=FIELD_SCORES)

        assert result["llm_called"] is True
        assert result["decision"] == "match"
        assert result["confidence"] == pytest.approx(0.88)
        assert result["score_override"] is not None  # pushed above high threshold

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_llm_no_match_decision(self, mock_litellm):
        llm_response = MagicMock()
        llm_response.choices[0].message.content = json.dumps({
            "decision": "no_match",
            "confidence": 0.92,
            "reasoning": "Same name, completely different businesses.",
        })
        mock_litellm.completion.return_value = llm_response

        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.70, field_scores=FIELD_SCORES)

        assert result["decision"] == "no_match"
        assert result["score_override"] is not None
        assert result["score_override"] < 0.55  # pushed below low threshold

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_fallback_on_llm_error(self, mock_litellm):
        mock_litellm.completion.side_effect = RuntimeError("API timeout")

        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.70)

        # Should not raise; falls back gracefully
        assert result["decision"] in {"match", "no_match"}
        assert result["llm_called"] is False
        assert "error" in result

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_handles_markdown_fenced_json(self, mock_litellm):
        llm_response = MagicMock()
        llm_response.choices[0].message.content = (
            "```json\n{\"decision\": \"match\", \"confidence\": 0.9, \"reasoning\": \"test\"}\n```"
        )
        mock_litellm.completion.return_value = llm_response

        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.70)
        assert result["decision"] == "match"

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_verify_batch(self, mock_litellm):
        llm_response = MagicMock()
        llm_response.choices[0].message.content = json.dumps({
            "decision": "match", "confidence": 0.9, "reasoning": "ok"
        })
        mock_litellm.completion.return_value = llm_response

        v = self._verifier()
        pairs = [
            (RECORD_A, RECORD_B, 0.95),   # fast path — no LLM
            (RECORD_A, RECORD_B, 0.70),   # LLM called
            (RECORD_A, RECORD_B, 0.30),   # fast path — no LLM
        ]
        results = v.verify_batch(pairs)
        assert len(results) == 3
        assert results[0]["llm_called"] is False
        assert results[1]["llm_called"] is True
        assert results[2]["llm_called"] is False


class TestLLMHardening:
    def _verifier(self, **kwargs):
        from entity_resolution.reasoning.llm_verifier import LLMMatchVerifier
        return LLMMatchVerifier(model="test/model", api_key="test-key", **kwargs)

    def _resp(self, content):
        r = MagicMock()
        r.choices[0].message.content = content
        return r

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_parse_failure_retries_then_routes_to_review(self, mock_litellm):
        mock_litellm.completion.return_value = self._resp("not json at all")
        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.70)
        assert result["decision"] == "error"
        assert result["needs_review"] is True
        # never fabricates match/no_match from the raw score
        assert v.stats()["parse_failures"] == 1
        assert mock_litellm.completion.call_count == 2  # initial + one retry

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_parse_failure_recovers_on_retry(self, mock_litellm):
        good = json.dumps({"decision": "match", "confidence": 0.9, "reasoning": "ok"})
        mock_litellm.completion.side_effect = [self._resp("garbage"), self._resp(good)]
        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.70)
        assert result["decision"] == "match"
        assert v.stats()["parse_failures"] == 0

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_empty_fenced_block_does_not_crash(self, mock_litellm):
        mock_litellm.completion.return_value = self._resp("```\n\n```")
        v = self._verifier()
        result = v.verify(RECORD_A, RECORD_B, score=0.70)  # must not raise
        assert result["decision"] == "error"

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_max_calls_budget_routes_remaining_to_review(self, mock_litellm):
        good = json.dumps({"decision": "match", "confidence": 0.9, "reasoning": "ok"})
        mock_litellm.completion.return_value = self._resp(good)
        v = self._verifier(max_calls=1)
        first = v.verify(RECORD_A, RECORD_B, score=0.70)
        second = v.verify(RECORD_A, RECORD_B, score=0.70)
        assert first["llm_called"] is True
        assert second["decision"] == "pending_review"
        assert second["llm_called"] is False
        assert v.stats()["budget_stops"] == 1
        assert mock_litellm.completion.call_count == 1  # second never called the LLM

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_stats_count_calls(self, mock_litellm):
        good = json.dumps({"decision": "no_match", "confidence": 0.8, "reasoning": "x"})
        mock_litellm.completion.return_value = self._resp(good)
        v = self._verifier()
        v.verify(RECORD_A, RECORD_B, score=0.70)
        v.verify(RECORD_A, RECORD_B, score=0.72)
        assert v.stats()["calls"] == 2

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_mask_fields_hides_pii_from_prompt(self, mock_litellm):
        good = json.dumps({"decision": "match", "confidence": 0.9, "reasoning": "ok"})
        mock_litellm.completion.return_value = self._resp(good)
        a = {"name": "Acme", "ssn": "123-45-6789"}
        b = {"name": "Acme", "ssn": "123-45-6789"}
        v = self._verifier(mask_fields=["ssn"])
        v.verify(a, b, score=0.70)
        prompt = mock_litellm.completion.call_args.kwargs["messages"][0]["content"]
        assert "123-45-6789" not in prompt
        assert "masked:" in prompt

    def test_estimate_cost_returns_structure(self):
        v = self._verifier()
        est = v.estimate_cost(num_pairs=100)
        assert est["num_pairs"] == 100
        assert "cost_usd" in est


class TestResponseBudget:
    """The response budget must fit a verdict a verbose model actually writes.

    This was hardcoded at 256 tokens. The verdict is JSON whose ``reasoning``
    field is free text, so a model that explains itself at length runs past the
    cap mid-string, the truncated JSON fails to parse, and the verdict is thrown
    away — the pair is routed to human review as though the model was never
    asked. Measured on 200 ambiguous Amazon-Google pairs: gemini-3.8-flash lost
    57 of 200 verdicts (28%) at 256 tokens and 1 of 200 at 1024.

    It was invisible because terse models don't trigger it — claude-opus-5 lost
    5 and a local llama3.1:8b lost none. Only a verbose model exposes it, which
    is why these tests simulate truncation rather than asserting a constant.
    """

    def _verifier(self, **kwargs):
        from entity_resolution.reasoning.llm_verifier import LLMMatchVerifier
        return LLMMatchVerifier(model="test/model", api_key="test-key", **kwargs)

    @staticmethod
    def _truncating_completion(reasoning_chars: int):
        """A fake boundary that truncates like a real one: at max_tokens.

        Roughly four characters per token, which is the usual English ratio and
        close enough to reproduce the failure at the boundary that matters.
        """
        def _complete(**kwargs):
            body = json.dumps({
                "decision": "match",
                "confidence": 0.9,
                "reasoning": "x" * reasoning_chars,
            })
            budget_chars = int(kwargs["max_tokens"]) * 4
            resp = MagicMock()
            resp.choices[0].message.content = body[:budget_chars]
            return resp
        return _complete

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_verbose_verdict_survives_the_default_budget(self, mock_litellm):
        """The regression: a long but legitimate verdict must still parse."""
        mock_litellm.completion.side_effect = self._truncating_completion(1500)
        v = self._verifier(low_threshold=0.55, high_threshold=0.80)

        result = v.verify(RECORD_A, RECORD_B, score=0.70)

        assert result["decision"] == "match", (
            "a verbose verdict was truncated and discarded; the response budget "
            "is too small for the JSON the model actually returns"
        )
        assert result.get("needs_review") is not True

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_a_too_small_budget_really_does_destroy_the_verdict(self, mock_litellm):
        """Proves the test above is load-bearing rather than vacuously green.

        With the old 256-token budget the same response is lost, so the
        simulation reproduces the measured failure instead of merely passing.
        """
        mock_litellm.completion.side_effect = self._truncating_completion(1500)
        v = self._verifier(low_threshold=0.55, high_threshold=0.80,
                           max_response_tokens=256)

        result = v.verify(RECORD_A, RECORD_B, score=0.70)

        assert result["decision"] == "error"
        assert result["needs_review"] is True

    @patch("entity_resolution.reasoning.llm_verifier.litellm")
    def test_request_carries_the_configured_budget(self, mock_litellm):
        """The setting must reach the provider, not just be stored."""
        mock_litellm.completion.side_effect = self._truncating_completion(20)
        v = self._verifier(low_threshold=0.55, high_threshold=0.80,
                           max_response_tokens=2048)

        v.verify(RECORD_A, RECORD_B, score=0.70)

        assert mock_litellm.completion.call_args.kwargs["max_tokens"] == 2048

    def test_budget_below_the_floor_is_rejected(self):
        """A budget too small for any verdict is a configuration error.

        Failing at construction beats discovering it as a mysterious stream of
        'unparseable output' warnings in production.
        """
        with pytest.raises(ValueError, match="max_response_tokens"):
            self._verifier(max_response_tokens=16)

    def test_default_budget_is_not_the_broken_value(self):
        v = self._verifier()
        assert v.max_response_tokens >= 512
