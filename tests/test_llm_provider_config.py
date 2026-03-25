"""Tests for LLMProviderConfig, ActiveLearningConfig.llm, and LLMMatchVerifier wiring."""

from __future__ import annotations

import pytest

from entity_resolution.config.er_config import (
    ActiveLearningConfig,
    LLMProviderConfig,
)


# ---------------------------------------------------------------------------
# LLMProviderConfig
# ---------------------------------------------------------------------------

class TestLLMProviderConfig:
    def test_defaults(self):
        cfg = LLMProviderConfig()
        assert cfg.provider == "openrouter"
        assert cfg.model is None
        assert cfg.base_url is None
        assert cfg.timeout_seconds == 60

    def test_ollama_defaults_base_url(self):
        cfg = LLMProviderConfig(provider="ollama", model="llama3.1:8b")
        assert cfg.base_url == "http://localhost:11434"

    def test_explicit_base_url_overrides_default(self):
        cfg = LLMProviderConfig(
            provider="ollama", model="llama3.1:8b", base_url="http://remote:11434"
        )
        assert cfg.base_url == "http://remote:11434"

    def test_to_litellm_model_string_ollama(self):
        cfg = LLMProviderConfig(provider="ollama", model="mistral")
        assert cfg.to_litellm_model_string() == "ollama/mistral"

    def test_to_litellm_model_string_openrouter(self):
        cfg = LLMProviderConfig(provider="openrouter", model="google/gemini-2.0-flash")
        assert cfg.to_litellm_model_string() == "openrouter/google/gemini-2.0-flash"

    def test_to_litellm_model_string_none_when_no_model(self):
        cfg = LLMProviderConfig(provider="openai")
        assert cfg.to_litellm_model_string() is None

    def test_from_dict(self):
        d = {"provider": "anthropic", "model": "claude-3", "timeout_seconds": 30}
        cfg = LLMProviderConfig.from_dict(d)
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-3"
        assert cfg.timeout_seconds == 30

    def test_to_dict_round_trip(self):
        cfg = LLMProviderConfig(
            provider="ollama", model="mistral", timeout_seconds=45
        )
        d = cfg.to_dict()
        cfg2 = LLMProviderConfig.from_dict(d)
        assert cfg2.provider == cfg.provider
        assert cfg2.model == cfg.model
        assert cfg2.timeout_seconds == cfg.timeout_seconds

    def test_validate_accepts_valid_providers(self):
        for p in LLMProviderConfig.VALID_PROVIDERS:
            cfg = LLMProviderConfig(provider=p)
            assert cfg.validate() == []

    def test_validate_rejects_unknown_provider(self):
        cfg = LLMProviderConfig(provider="bogus")
        errors = cfg.validate()
        assert any("bogus" in e for e in errors)

    def test_validate_rejects_bad_timeout(self):
        cfg = LLMProviderConfig(timeout_seconds=0)
        errors = cfg.validate()
        assert any("timeout" in e for e in errors)


# ---------------------------------------------------------------------------
# ActiveLearningConfig.llm integration
# ---------------------------------------------------------------------------

class TestActiveLearningConfigLLM:
    def test_effective_model_string_prefers_llm(self):
        llm = LLMProviderConfig(provider="ollama", model="mistral")
        cfg = ActiveLearningConfig(model="openrouter/fallback", llm=llm)
        assert cfg.effective_model_string() == "ollama/mistral"

    def test_effective_model_string_falls_back_to_model(self):
        cfg = ActiveLearningConfig(model="openai/gpt-4o")
        assert cfg.effective_model_string() == "openai/gpt-4o"

    def test_effective_model_string_none_when_both_unset(self):
        cfg = ActiveLearningConfig()
        assert cfg.effective_model_string() is None

    def test_from_dict_with_llm_section(self):
        d = {
            "enabled": True,
            "model": "legacy-model",
            "llm": {"provider": "ollama", "model": "llama3.1:8b"},
        }
        cfg = ActiveLearningConfig.from_dict(d)
        assert cfg.llm is not None
        assert cfg.llm.provider == "ollama"
        assert cfg.effective_model_string() == "ollama/llama3.1:8b"

    def test_from_dict_without_llm_section(self):
        d = {"model": "openrouter/google/gemini-2.0-flash"}
        cfg = ActiveLearningConfig.from_dict(d)
        assert cfg.llm is None
        assert cfg.effective_model_string() == "openrouter/google/gemini-2.0-flash"

    def test_to_dict_includes_llm(self):
        llm = LLMProviderConfig(provider="ollama", model="mistral")
        cfg = ActiveLearningConfig(llm=llm)
        d = cfg.to_dict()
        assert "llm" in d
        assert d["llm"]["provider"] == "ollama"

    def test_validate_propagates_llm_errors(self):
        llm = LLMProviderConfig(provider="bogus", timeout_seconds=0)
        cfg = ActiveLearningConfig(llm=llm)
        errors = cfg.validate()
        assert any("bogus" in e for e in errors)
        assert any("timeout" in e for e in errors)


# ---------------------------------------------------------------------------
# LLMMatchVerifier.from_provider_config
# ---------------------------------------------------------------------------

class TestLLMMatchVerifierFromProviderConfig:
    def test_from_provider_config_sets_model(self):
        from entity_resolution.reasoning.llm_verifier import LLMMatchVerifier

        llm = LLMProviderConfig(provider="ollama", model="mistral")
        verifier = LLMMatchVerifier.from_provider_config(llm)
        assert verifier.model == "ollama/mistral"
        assert verifier.base_url == "http://localhost:11434"
        assert verifier.timeout_seconds == 60

    def test_from_provider_config_passes_kwargs(self):
        from entity_resolution.reasoning.llm_verifier import LLMMatchVerifier

        llm = LLMProviderConfig(provider="openai", model="gpt-4o")
        verifier = LLMMatchVerifier.from_provider_config(
            llm, low_threshold=0.5, high_threshold=0.9, entity_type="company"
        )
        assert verifier.low_threshold == 0.5
        assert verifier.high_threshold == 0.9
        assert verifier.entity_type == "company"
