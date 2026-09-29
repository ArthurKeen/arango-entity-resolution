"""The pipeline's LLM verifier must be built from the config the user wrote.

ActiveLearningConfig parsed and validated a structured ``llm:`` block (provider,
base_url, timeout, api_key_env, healthcheck_on_start), and the pipeline then
built its verifier from the bare ``model`` string alone. A README-style config
naming ``provider: ollama`` therefore produced a verifier with no model and
litellm's default endpoint. ``mask_fields``, the one control over which values
leave the network, had no config key at all.

The pipeline and verifier here are real. Only the database and the LLM API,
the external boundaries, are faked.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from entity_resolution.config.er_config import ERPipelineConfig
from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline


class _DB:
    """Enough of a database for construction. Not a MagicMock."""

    name = "wiring_test_db"

    def __init__(self) -> None:
        self.created = []

    def has_collection(self, name):
        return name in self.created

    def create_collection(self, name, **kwargs):
        self.created.append(name)


def _pipeline(active_learning: Dict[str, Any]) -> ConfigurableERPipeline:
    config = ERPipelineConfig.from_dict({
        "entity_resolution": {
            "collection_name": "companies",
            "blocking": {"strategy": "exact", "fields": [{"field": "name"}]},
            "active_learning": {"enabled": True, **active_learning},
        }
    })
    return ConfigurableERPipeline(db=_DB(), config=config)


def test_structured_llm_block_reaches_the_verifier(monkeypatch) -> None:
    monkeypatch.setenv("MY_LLM_KEY", "k-123")
    pipeline = _pipeline({
        "llm": {"provider": "ollama", "model": "llama3.1:8b", "timeout_seconds": 45,
                "api_key_env": "MY_LLM_KEY", "healthcheck_on_start": False},
        "mask_fields": ["ssn", "email"],
    })
    verifier = pipeline._build_active_learning_verifier().verifier
    assert verifier.model == "ollama/llama3.1:8b"
    assert verifier.base_url == "http://localhost:11434"
    assert verifier.timeout_seconds == 45
    assert verifier.api_key == "k-123"
    assert verifier.mask_fields == {"ssn", "email"}


def test_masked_fields_do_not_reach_the_provider(monkeypatch) -> None:
    import litellm

    sent = []

    def capture(**kwargs):  # the LLM API is the external boundary
        sent.append(kwargs)
        raise ConnectionError("not calling out in a unit test")

    monkeypatch.setattr(litellm, "completion", capture)
    pipeline = _pipeline({"model": "openai/gpt-4o", "mask_fields": ["ssn"]})
    verifier = pipeline._build_active_learning_verifier().verifier
    verifier.verify({"name": "Ann Lee", "ssn": "123-45-6789"},
                    {"name": "Ann Lee", "ssn": "123-45-6789"}, 0.7)
    assert sent, "the in-band pair should have been sent for verification"
    payload = str(sent[0]["messages"])
    assert "Ann Lee" in payload
    assert "123-45-6789" not in payload


def test_mask_fields_round_trips_and_validates() -> None:
    config = ERPipelineConfig.from_dict({"entity_resolution": {
        "active_learning": {"enabled": True, "mask_fields": ["ssn"]}}})
    assert config.to_dict()["entity_resolution"]["active_learning"]["mask_fields"] == ["ssn"]
    bad = ERPipelineConfig.from_dict({"entity_resolution": {
        "active_learning": {"enabled": True, "mask_fields": [""]}}})
    assert any("mask_fields" in e for e in bad.active_learning.validate())


def test_healthcheck_on_start_runs_and_is_reported(monkeypatch) -> None:
    import litellm

    calls = []

    def unreachable(**kwargs):  # the LLM API is the external boundary
        calls.append(kwargs)
        raise ConnectionError("connection refused")

    monkeypatch.setattr(litellm, "completion", unreachable)
    pipeline = _pipeline({"llm": {"provider": "ollama", "model": "llama3.1:8b",
                                  "healthcheck_on_start": True}})
    pipeline._build_active_learning_verifier()
    assert calls and calls[0]["model"] == "ollama/llama3.1:8b"
    assert pipeline._llm_healthcheck["ok"] is False
