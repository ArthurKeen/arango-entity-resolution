"""Unit tests for GraphEmbeddingBlockingStrategy + config (plan 3.4)."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from entity_resolution.config.er_config import BlockingConfig, ERPipelineConfig
from entity_resolution.strategies.graph_embedding_blocking import (
    GraphEmbeddingBlockingStrategy,
)

VEC_INDEX_NODE = {"type": "vector", "fields": ["node_embedding"], "params": {"dimension": 64}}


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def next(self):
        return self._rows[0]

    def __iter__(self):
        return iter(self._rows)


class _FakeColl:
    def __init__(self, indexes):
        self._indexes = list(indexes)

    def indexes(self):
        return self._indexes

    def count(self):
        return 10


class _FakeAQL:
    def __init__(self, coverage, pairs):
        self.calls: List[Dict[str, Any]] = []
        self._coverage = coverage
        self._pairs = pairs

    def execute(self, query, bind_vars=None, **kwargs):
        q = str(query)
        self.calls.append({"query": q})
        if "coverage_percent" in q:
            return _FakeCursor([self._coverage])
        if "APPROX_NEAR_COSINE" in q:
            return _FakeCursor(self._pairs)
        return _FakeCursor([])


class _FakeDB:
    def __init__(self, indexes, coverage, pairs=None):
        self._coll = _FakeColl(indexes)
        self.aql = _FakeAQL(coverage, pairs or [])

    def properties(self):
        return {"version": "3.12.0"}

    def collection(self, name):
        return self._coll


def _cov(with_emb, total=10):
    return {
        "total": total, "with_embeddings": with_emb,
        "without_embeddings": total - with_emb,
        "coverage_percent": (with_emb / total * 100) if total else 0.0,
    }


def test_requires_edge_collection():
    with pytest.raises(ValueError, match="edge_collection"):
        GraphEmbeddingBlockingStrategy(
            _FakeDB([VEC_INDEX_NODE], _cov(10)), "people", edge_collection=""
        )


def test_ann_path_uses_node_embedding_field():
    pairs = [
        {"doc1_key": "1", "doc2_key": "2", "similarity": 0.9, "method": "arango_vector_index"},
        {"doc1_key": "2", "doc2_key": "1", "similarity": 0.9, "method": "arango_vector_index"},
    ]
    db = _FakeDB(indexes=[VEC_INDEX_NODE], coverage=_cov(10), pairs=pairs)
    strat = GraphEmbeddingBlockingStrategy(
        db=db, collection="people", edge_collection="worksAt",
        embedding_field="node_embedding", similarity_threshold=0.7,
        compute_embeddings=False, create_vector_index=False,
    )
    result = strat.generate_candidates()
    assert len(result) == 1  # reverse duplicate collapsed
    assert any("APPROX_NEAR_COSINE" in c["query"] for c in db.aql.calls)
    stats = strat.get_statistics()
    assert stats["strategy_name"] == "GraphEmbeddingBlockingStrategy"
    assert stats["total_pairs"] == 1


# --- config ---

def test_blocking_config_roundtrips_graph_embedding():
    cfg = BlockingConfig.from_dict({
        "strategy": "graph_embedding",
        "edge_collection": "worksAt",
        "create_vector_index": True,
        "node2vec_params": {"dimensions": 32, "walk_length": 8},
    })
    assert cfg.edge_collection == "worksAt"
    assert cfg.create_vector_index is True
    d = cfg.to_dict()
    assert d["edge_collection"] == "worksAt"
    assert d["node2vec_params"]["dimensions"] == 32


def test_validate_graph_embedding_requires_edge_collection():
    base = {"entity_type": "person", "collection_name": "people"}
    missing = ERPipelineConfig.from_dict({"entity_resolution": {
        **base, "blocking": {"strategy": "graph_embedding"}}})
    assert any("edge_collection" in e for e in missing.validate())

    ok = ERPipelineConfig.from_dict({"entity_resolution": {
        **base, "blocking": {"strategy": "graph_embedding", "edge_collection": "worksAt"}}})
    assert not any("blocking.strategy" in e for e in ok.validate())
    assert not any("edge_collection" in e for e in ok.validate())
