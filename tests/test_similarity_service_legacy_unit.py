from __future__ import annotations

import math

import pytest

from entity_resolution.services.similarity_service import SimilarityService


def test_similarity_service_emits_deprecation_warning_on_init() -> None:
    with pytest.warns(DeprecationWarning):
        SimilarityService()


def test_get_default_field_weights_contains_global_thresholds() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    w = svc.get_default_field_weights()
    assert "global" in w
    assert "upper_threshold" in w["global"]
    assert "lower_threshold" in w["global"]


def test_configure_field_weights_deep_merges() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    svc.configure_field_weights({"email_exact": {"importance": 9.9}, "new_field": {"m_prob": 0.5}})
    w = svc.get_field_weights()
    assert w["email_exact"]["importance"] == 9.9
    assert w["new_field"]["m_prob"] == 0.5


def test_ngram_similarity_edge_cases() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    assert svc._ngram_similarity("", "abc") == 0.0
    assert svc._ngram_similarity("abc", "abc") == 1.0
    # equality shortcut returns 1.0 even if shorter than n
    assert svc._ngram_similarity("ab", "ab", n=3) == 1.0


def test_normalized_levenshtein_distance_basic() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    assert svc._normalized_levenshtein("abc", "abc") == 1.0
    assert svc._normalized_levenshtein("", "abc") == 0.0
    assert svc._levenshtein_distance("kitten", "sitting") == 3


def test_jaro_and_jaro_winkler_ranges() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    j = svc._jaro_similarity("martha", "marhta")
    jw = svc._jaro_winkler_similarity("martha", "marhta")
    assert 0.0 <= j <= 1.0
    assert 0.0 <= jw <= 1.0
    assert jw >= j  # winkler adds prefix bonus above threshold


def test_soundex_and_phonetic_similarity() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    assert svc._soundex("") == "0000"
    assert svc._soundex("Robert").startswith("R")
    assert svc._phonetic_similarity("Robert", "Rupert") in (0.0, 1.0)


def test_compute_fellegi_sunter_score_match_and_details() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    similarities = {"email_exact": 1.0, "phone_exact": 1.0}
    weights = {
        "email_exact": {"m_prob": 0.95, "u_prob": 0.001, "threshold": 1.0, "importance": 1.0},
        "phone_exact": {"m_prob": 0.9, "u_prob": 0.005, "threshold": 1.0, "importance": 1.0},
        "global": {"upper_threshold": 0.1, "lower_threshold": -1.0},
    }
    out = svc._compute_fellegi_sunter_score(similarities, weights, include_details=True)
    assert out["success"] is True
    assert out["is_match"] is True
    assert out["decision"] == "match"
    assert "field_scores" in out and "statistics" in out
    assert out["statistics"]["fields_compared"] == 2


def test_compute_similarity_python_success_and_include_details() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    # We mostly care it computes and returns success + details.
    weights = svc.get_default_field_weights()
    weights["global"]["upper_threshold"] = 0.1
    weights["global"]["lower_threshold"] = -1.0

    a = {"first_name": "Jane", "last_name": "Doe", "email": "x@example.com", "phone": "555"}
    b = {"first_name": "Jane", "last_name": "Doe", "email": "x@example.com", "phone": "555"}
    out = svc.compute_similarity(a, b, field_weights=weights, include_details=True)
    assert out["success"] is True
    assert isinstance(out["confidence"], float)
    assert "field_scores" in out


def test_compute_batch_similarity_handles_missing_docs_and_stats() -> None:
    with pytest.warns(DeprecationWarning):
        svc = SimilarityService()
    weights = svc.get_default_field_weights()
    pairs = [
        {"docA": {"first_name": "A", "last_name": "B"}, "docB": {"first_name": "A", "last_name": "B"}},
        {"docA": {"first_name": "A"}, "docB": None},
    ]
    out = svc.compute_batch_similarity(pairs, field_weights=weights, include_details=False)
    assert out["success"] is True
    assert out["statistics"]["total_pairs"] == 2
    assert out["statistics"]["failed_pairs"] == 1
    assert len(out["results"]) == 2

