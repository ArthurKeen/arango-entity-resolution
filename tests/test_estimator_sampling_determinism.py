"""Seeded Fellegi-Sunter training must draw the same sample on every run.

Published FEBRL rows could not be reproduced: identical runs gave febrl1
multi-level 0.986 and 0.987. Three samples fed training unseeded. This covers
the two inside the estimator: the candidate-edge training sample and the
random-pair key draw, both ``SORT RAND()``. The third, the term-frequency table,
broke ties at its top-N cutoff arbitrarily.

AQL ``RAND()`` cannot be seeded, so a seed must change the query itself, and it
must hash something stable across runs. Edge ``_key``s are regenerated with
every blocking pass, so hashing them reproduced nothing; edges hash their
endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List

from entity_resolution.learning.model_parameter_estimator import ModelParameterEstimator


class _RecordingDB:
    """Records AQL and returns nothing. Not a MagicMock: unknown calls raise."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.aql = self

    def execute(self, query: str, bind_vars: Dict[str, Any] | None = None):
        self.calls.append({"query": query, "bind_vars": dict(bind_vars or {})})
        return iter([])


def _estimator(seed):
    db = _RecordingDB()
    est = ModelParameterEstimator(
        db=db, similarity_service=None, edge_collection="edges",
        field_names=["name"], random_pair_seed=seed,
    )
    return est, db


def test_seeded_training_sample_hashes_edge_endpoints() -> None:
    est, db = _estimator(7)
    est.sample_comparisons(100)
    (call,) = db.calls
    assert "RAND()" not in call["query"]
    assert "SHA1(CONCAT(@sample_seed, '|', e._from, '|', e._to))" in call["query"]
    assert call["bind_vars"]["sample_seed"] == "7"


def test_seeded_random_pair_draw_hashes_record_keys() -> None:
    est, db = _estimator(7)
    est.sample_random_pair_comparisons(100, "people")
    query = db.calls[0]["query"]
    assert "RAND()" not in query
    assert "SHA1(CONCAT(@sample_seed, '|', d._key))" in query


def test_unseeded_sampling_stays_random() -> None:
    est, db = _estimator(None)
    est.sample_comparisons(100)
    (call,) = db.calls
    assert "SORT RAND()" in call["query"]
    assert "sample_seed" not in call["bind_vars"]


def test_term_frequency_cutoff_breaks_ties_deterministically() -> None:
    est, db = _estimator(None)
    est.compute_term_frequencies("people", ["name"])
    tf_query = db.calls[0]["query"]
    assert "SORT cnt DESC, value ASC" in tf_query
