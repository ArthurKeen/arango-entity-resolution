"""Unit tests for GraphContextSimilarity + GraphContextConfig (plan 3.1)."""

from __future__ import annotations

import pytest

from entity_resolution.config.er_config import GraphContextConfig, SimilarityConfig
from entity_resolution.similarity.graph_context import GraphContextSimilarity


def _svc(**kw):
    return GraphContextSimilarity(
        db=None, vertex_collection="Person", edge_collections=["worksAt"], **kw
    )


# --- pair_features (pure, no DB) ---

def test_shared_neighbor_and_jaccard():
    svc = _svc()
    cache = {"a": {"Org/1", "Org/2"}, "b": {"Org/2", "Org/3"}}
    f = svc.pair_features("a", "b", cache)
    assert f["graph_shared_neighbor_count"] == pytest.approx(1 / 5)  # 1 shared / saturation 5
    assert f["graph_neighbor_jaccard"] == pytest.approx(1 / 3)
    assert f["graph_path_within_k"] == 1.0  # shared neighbour => length-2 path


def test_no_overlap_is_zero():
    svc = _svc()
    cache = {"a": {"Org/1"}, "b": {"Org/9"}}
    f = svc.pair_features("a", "b", cache)
    assert f["graph_shared_neighbor_count"] == 0.0
    assert f["graph_neighbor_jaccard"] == 0.0
    assert f["graph_path_within_k"] == 0.0


def test_direct_edge_sets_path_within_k():
    svc = _svc()
    # b's own vertex id appears in a's neighbour set => direct edge (length 1).
    cache = {"a": {"Person/b"}, "b": {"Person/a"}}
    f = svc.pair_features("a", "b", cache)
    assert f["graph_path_within_k"] == 1.0


def test_count_saturation_caps_at_one():
    svc = _svc(count_saturation=3)
    shared = {f"Org/{i}" for i in range(10)}
    cache = {"a": shared, "b": shared}
    f = svc.pair_features("a", "b", cache)
    assert f["graph_shared_neighbor_count"] == 1.0  # min(10,3)/3
    assert f["graph_neighbor_jaccard"] == 1.0


def test_feature_field_names_namespaced():
    svc = _svc(features=["neighbor_jaccard"])
    assert svc.feature_field_names() == ["graph_neighbor_jaccard"]
    f = svc.pair_features("a", "b", {"a": {"Org/1"}, "b": {"Org/1"}})
    assert set(f) == {"graph_neighbor_jaccard"}


# --- GraphContextConfig ---

def test_config_from_dict_none_returns_none():
    assert GraphContextConfig.from_dict(None) is None
    assert GraphContextConfig.from_dict({}) is None


def test_config_from_dict_and_enabled():
    cfg = GraphContextConfig.from_dict(
        {"edge_collections": ["worksAt"], "max_hops": 2, "features": ["neighbor_jaccard"]}
    )
    assert cfg is not None and cfg.enabled
    assert cfg.to_dict()["edge_collections"] == ["worksAt"]


def test_config_validate_rejects_bad_values():
    bad = GraphContextConfig(edge_collections=["e"], max_hops=9, features=["bogus"])
    errors = bad.validate()
    assert any("max_hops" in e for e in errors)
    assert any("features" in e for e in errors)


def test_similarity_config_roundtrips_graph_context():
    sc = SimilarityConfig.from_dict(
        {"algorithm": "jaro_winkler", "graph_context": {"edge_collections": ["worksAt"]}}
    )
    assert sc.graph_context is not None
    assert "graph_context" in sc.to_dict()
