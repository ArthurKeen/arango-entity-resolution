from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from entity_resolution.strategies.vector_blocking import VectorBlockingStrategy


class _FakeCursor:
    def __init__(self, rows: List[Any]):
        self._rows = list(rows)

    def next(self):
        return self._rows[0]

    def __iter__(self):
        return iter(self._rows)


class _FakeAQL:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self._responses: List[List[Any]] = []

    def queue(self, rows: List[Any]) -> None:
        self._responses.append(rows)

    def execute(self, query, bind_vars=None, **kwargs):
        self.calls.append({"query": str(query), "bind_vars": dict(bind_vars or {}), "kwargs": dict(kwargs)})
        rows = self._responses.pop(0) if self._responses else []
        return _FakeCursor(rows)


class _FakeDB:
    def __init__(self):
        self.aql = _FakeAQL()


def test_generate_candidates_raises_if_no_embeddings() -> None:
    db = _FakeDB()
    # _check_embeddings_exist cursor.next() should return dict
    db.aql.queue([{"total": 10, "with_embeddings": 0, "without_embeddings": 10, "coverage_percent": 0.0}])

    strat = VectorBlockingStrategy(db=db, collection="customers", use_ann_adapter=False)
    with pytest.raises(RuntimeError, match="No embeddings found"):
        strat.generate_candidates()


def test_generate_candidates_uses_legacy_when_ann_disabled_and_normalizes_pairs() -> None:
    db = _FakeDB()
    db.aql.queue([{"total": 2, "with_embeddings": 2, "without_embeddings": 0, "coverage_percent": 100.0}])
    # legacy query returns duplicates; normalize should de-dup
    db.aql.queue(
        [
            {"doc1_key": "1", "doc2_key": "2", "similarity": 0.9, "method": "vector"},
            {"doc1_key": "1", "doc2_key": "2", "similarity": 0.9, "method": "vector"},
        ]
    )

    strat = VectorBlockingStrategy(
        db=db,
        collection="customers",
        use_ann_adapter=False,
        similarity_threshold=0.7,
        limit_per_entity=10,
        filters={"state": {"equals": "CA"}},
    )
    pairs = strat.generate_candidates()
    assert len(pairs) == 1
    assert pairs[0]["doc1_key"] == "1"
    assert pairs[0]["doc2_key"] == "2"

    # validate bind vars include filter bind var and similarity config
    legacy_call = db.aql.calls[-1]
    assert legacy_call["bind_vars"]["similarity_threshold"] == 0.7
    assert legacy_call["bind_vars"]["limit_per_entity"] == 10
    assert legacy_call["bind_vars"]["filter_state_equals"] == "CA"


def test_generate_candidates_falls_back_when_ann_adapter_throws() -> None:
    db = _FakeDB()
    db.aql.queue([{"total": 1, "with_embeddings": 1, "without_embeddings": 0, "coverage_percent": 100.0}])
    db.aql.queue([{"doc1_key": "a", "doc2_key": "b", "similarity": 0.8, "method": "vector"}])

    strat = VectorBlockingStrategy(db=db, collection="customers", use_ann_adapter=False)
    # simulate ann enabled but failing by manually setting properties
    strat.use_ann_adapter = True

    class _BadANN:
        method = "fake_ann"

        def find_all_pairs(self, **kwargs):
            raise RuntimeError("ann broke")

    strat.ann_adapter = _BadANN()
    pairs = strat.generate_candidates()
    assert pairs and pairs[0]["doc1_key"] == "a"


def test_generate_candidates_optimized_raises_not_implemented() -> None:
    db = _FakeDB()
    strat = VectorBlockingStrategy(db=db, collection="customers", use_ann_adapter=False)
    with pytest.raises(NotImplementedError):
        strat.generate_candidates_optimized()


def test_get_similarity_distribution_returns_error_when_empty() -> None:
    db = _FakeDB()
    db.aql.queue([])  # distribution empty
    strat = VectorBlockingStrategy(db=db, collection="customers", use_ann_adapter=False)
    out = strat.get_similarity_distribution(sample_size=10)
    assert "error" in out


def test_get_similarity_distribution_computes_stats_when_nonempty() -> None:
    db = _FakeDB()
    # buckets: 0.7 count 2, 0.9 count 1 -> midpoints 0.75,0.75,0.95
    db.aql.queue([{"bucket": 0.7, "count": 2}, {"bucket": 0.9, "count": 1}])
    strat = VectorBlockingStrategy(db=db, collection="customers", use_ann_adapter=False)
    out = strat.get_similarity_distribution(sample_size=3)
    assert out["sample_size"] == 3
    assert 0.7 <= out["min_similarity"] <= out["max_similarity"] <= 1.0
    assert "recommended_thresholds" in out


def test_repr_contains_collection_and_params() -> None:
    db = _FakeDB()
    strat = VectorBlockingStrategy(db=db, collection="customers", similarity_threshold=0.8, limit_per_entity=5, use_ann_adapter=False)
    s = repr(strat)
    assert "customers" in s
    assert "0.8" in s

