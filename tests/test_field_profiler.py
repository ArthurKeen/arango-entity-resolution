"""Unit tests for schema-agnostic field profiling (plan 1.4)."""

from __future__ import annotations

import pytest

from entity_resolution.learning.field_profiler import (
    FieldProfiler,
    _sample_values,
    classify_values,
    field_config,
)


def _type(values):
    return classify_values(values)["type"]


def test_sample_values_distinct_and_capped():
    vals = ["Acme", "Acme", "Beta", None, "  ", "Gamma", "Delta"]
    out = _sample_values(vals, limit=3)
    assert out == ["Acme", "Beta", "Gamma"]  # distinct, non-empty, capped, order-preserving


def test_sample_values_truncates_long_strings():
    out = _sample_values(["x" * 500], limit=3)
    assert len(out[0]) == 120


def test_classifies_email():
    assert _type([f"user{i}@example.com" for i in range(20)]) == "email"


def test_classifies_phone():
    assert _type(["+1 (555) 123-4567", "555-987-6543", "(212) 555 0100"] * 5) == "phone"


def test_classifies_date():
    assert _type(["2024-01-01", "2023-12-31", "2020-06-15"] * 5) == "date"


def test_classifies_numeric():
    assert _type([str(i) for i in range(20)]) == "numeric"


def test_classifies_person_name():
    names = ["John Smith", "Jane Doe", "Bob Martinez", "Alice Walker", "Carl Yu"] * 4
    assert _type(names) == "person_name"


def test_classifies_org_name():
    orgs = ["Acme Inc", "Globex LLC", "Initech Corp", "Umbrella Corporation"] * 5
    assert _type(orgs) == "org_name"


def test_classifies_address():
    addrs = ["123 Main St", "456 Oak Avenue", "789 Elm Road", "12 Pine Blvd"] * 5
    assert _type(addrs) == "address"


def test_classifies_free_text():
    texts = ["This is a fairly long descriptive sentence about the entity in question."] * 10
    assert _type(texts) == "free_text"


def test_empty_values_default_free_text():
    assert _type([None, "", "   "]) == "free_text"


def test_field_config_has_comparator_and_priors():
    cfg = field_config("email", "email")
    assert cfg["algorithm"] == "jaro_winkler"
    assert "lower" in cfg["transformers"]
    assert cfg["m_prior"] > cfg["u_prior"]
    assert 0.0 < cfg["agreement_threshold"] <= 1.0


def test_phone_config_uses_digits_only():
    assert "digits_only" in field_config("phone", "phone")["transformers"]


class TestEmitConfig:
    def _profiler_with(self, profile):
        prof = FieldProfiler(db=None, collection="x")
        return prof.emit_similarity_config(profile)

    def test_emits_normalized_weights_and_skips_freetext(self):
        profile = {
            "collection": "people",
            "sampled_docs": 100,
            "fields": {
                "name": {"type": "person_name", "completeness": 1.0,
                         "stats": {}, "config": field_config("name", "person_name")},
                "email": {"type": "email", "completeness": 0.9,
                          "stats": {}, "config": field_config("email", "email")},
                "bio": {"type": "free_text", "completeness": 0.8,
                        "stats": {}, "config": field_config("bio", "free_text")},
                "rare": {"type": "person_name", "completeness": 0.1,
                         "stats": {}, "config": field_config("rare", "person_name")},
            },
        }
        out = self._profiler_with(profile)["similarity"]
        weights = out["field_weights"]
        assert "bio" not in weights       # free_text excluded
        assert "rare" not in weights      # below min_completeness
        assert set(weights) == {"name", "email"}
        assert abs(sum(weights.values()) - 1.0) < 1e-3  # normalized (rounded seeds)
        assert out["agreement_thresholds"]["email"] == 0.95
        assert "lower" in out["transformers"]["email"]
        assert out["m_priors"]["name"] > out["u_priors"]["name"]


# ---------------------------------------------------------------------------
# arango-solutions-org/arango-entity-resolution#2: vectors and phrases
# ---------------------------------------------------------------------------

_PHRASES = [
    "DATA PRIVACY REGULATIONS", "DATA PRIVACY LAWS AND REGULATIONS",
    "SUPPLY CHAIN DISRUPTION RISK", "FOREIGN CURRENCY EXCHANGE RATES",
    "INTEREST RATE RISK", "CYBERSECURITY INCIDENT RESPONSE PLAN",
    "CLIMATE RELATED FINANCIAL DISCLOSURES", "REVENUE RECOGNITION POLICY",
] * 6


def _vectors(n=50, dims=512):
    import random

    rng = random.Random(0)
    return [[rng.uniform(-1, 1) for _ in range(dims)] for _ in range(n)]


def test_numeric_vectors_are_typed_vector_not_address():
    # Stringified, a list of floats has digits and many tokens, so it was typed
    # "address" and compared with Jaro-Winkler at weight 0.7.
    result = classify_values(_vectors())
    assert result["type"] == "vector"
    assert result["stats"]["dimensions"] == 512
    assert classify_values([tuple(v) for v in _vectors(dims=8)])["type"] == "vector"
    assert classify_values([[1, 2, 3]] * 10)["type"] == "vector"


def test_lists_that_are_not_numeric_vectors_are_not_vectors():
    assert _type([["a", "b"]] * 10) != "vector"
    assert _type([[True, False]] * 10) != "vector"
    # Mostly-scalar fields with the odd stray list stay what they were.
    assert _type(["123 Main St", "456 Oak Avenue"] * 9 + [[0.1, 0.2]]) == "address"


def test_multi_word_labels_are_phrases_compared_by_tokens():
    assert _type(_PHRASES) == "phrase"
    cfg = field_config("label", "phrase")
    assert cfg["algorithm"] == "jaccard"
    # The boundaries this must not move.
    assert _type(["John Smith", "Jane Doe", "Bob Martinez"] * 5) == "person_name"
    assert _type(["This is a fairly long descriptive sentence about the entity."] * 5) == "free_text"


def test_emitted_config_carries_algorithms_and_says_what_it_left_out():
    profile = {"collection": "topics", "sampled_docs": 50, "fields": {
        "label": {"type": "phrase", "completeness": 1.0, "stats": {}, "config": field_config("label", "phrase")},
        "phone": {"type": "phone", "completeness": 1.0, "stats": {}, "config": field_config("phone", "phone")},
        "name": {"type": "person_name", "completeness": 1.0, "stats": {}, "config": field_config("name", "person_name")},
        "embedding": {"type": "vector", "completeness": 1.0, "stats": {"dimensions": 512},
                      "config": field_config("embedding", "vector")},
    }}
    out = FieldProfiler(db=None, collection="topics").emit_similarity_config(profile)
    sim = out["similarity"]
    assert "embedding" not in sim["field_weights"]
    assert sim["field_algorithms"] == {"label": "jaccard", "phone": "levenshtein"}
    assert "512 dimensions" in out["excluded_fields"]["embedding"]
    assert "blocking.strategy 'vector'" in out["excluded_fields"]["embedding"]


def test_emitted_phrase_algorithm_reaches_the_scorer():
    # The profiler always chose a per-field algorithm, but the emitted config
    # had nowhere to put it: every field was compared with Jaro-Winkler. Load
    # the emitted config through the real loader and pipeline and score.
    from entity_resolution.config.er_config import ERPipelineConfig
    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    profile = {"collection": "topics", "sampled_docs": 48, "fields": {
        "label": {"type": "phrase", "completeness": 1.0, "stats": {}, "config": field_config("label", "phrase")},
    }}
    emitted = FieldProfiler(db=None, collection="topics").emit_similarity_config(profile)
    config = ERPipelineConfig.from_dict({"entity_resolution": {
        "collection_name": "topics",
        "blocking": {"strategy": "exact", "fields": ["label"]},
        **emitted,
    }})
    assert config.validate() == []
    assert config.to_dict()["entity_resolution"]["similarity"]["field_algorithms"] == {"label": "jaccard"}

    service = ConfigurableERPipeline(db=None, config=config).build_similarity_service()
    scores = service.similarity_computer.compute_detailed(
        {"label": "DATA PRIVACY REGULATIONS"}, {"label": "DATA PRIVACY LAWS AND REGULATIONS"}
    )["field_scores"]
    assert scores["label"] == pytest.approx(0.6)  # 3 shared / 5 tokens; Jaro-Winkler gives 0.90


def test_invalid_field_algorithm_is_a_validation_error():
    from entity_resolution.config.er_config import ERPipelineConfig

    config = ERPipelineConfig.from_dict({"entity_resolution": {
        "blocking": {"strategy": "exact", "fields": ["label"]},
        "similarity": {"field_algorithms": {"label": "cosine"}},
    }})
    assert any("field_algorithms['label']" in e for e in config.validate())
