"""Tests for LLMMatchVerifier.healthcheck()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestHealthcheck:
    def _make_verifier(self, **kwargs):
        from entity_resolution.reasoning.llm_verifier import LLMMatchVerifier
        return LLMMatchVerifier(model="test/model", **kwargs)

    def test_healthcheck_ok(self):
        verifier = self._make_verifier()
        mock_response = MagicMock()

        with patch("entity_resolution.reasoning.llm_verifier.litellm") as mock_litellm:
            mock_litellm.completion.return_value = mock_response
            result = verifier.healthcheck()

        assert result["ok"] is True
        assert result["model"] == "test/model"
        assert isinstance(result["latency_ms"], float)
        assert result["error"] is None

    def test_healthcheck_failure(self):
        verifier = self._make_verifier()

        with patch("entity_resolution.reasoning.llm_verifier.litellm") as mock_litellm:
            mock_litellm.completion.side_effect = ConnectionError("refused")
            result = verifier.healthcheck()

        assert result["ok"] is False
        assert result["model"] == "test/model"
        assert result["latency_ms"] is None
        assert "refused" in result["error"]

    def test_healthcheck_timeout(self):
        verifier = self._make_verifier()

        with patch("entity_resolution.reasoning.llm_verifier.litellm") as mock_litellm:
            mock_litellm.completion.side_effect = TimeoutError("timed out")
            result = verifier.healthcheck()

        assert result["ok"] is False
        assert "timed out" in result["error"]

    def test_healthcheck_passes_base_url(self):
        verifier = self._make_verifier(base_url="http://localhost:11434")

        with patch("entity_resolution.reasoning.llm_verifier.litellm") as mock_litellm:
            mock_litellm.completion.return_value = MagicMock()
            verifier.healthcheck()
            call_kwargs = mock_litellm.completion.call_args[1]
            assert call_kwargs.get("api_base") == "http://localhost:11434"
