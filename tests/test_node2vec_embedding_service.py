from __future__ import annotations

from typing import List, Tuple

import numpy as np

from entity_resolution.services.node2vec_embedding_service import Node2VecEmbeddingService, Node2VecParams


def _toy_edges() -> List[Tuple[str, str, float]]:
    # Triangle + tail: a-b-c-a and c-d
    return [
        ("v/a", "v/b", 1.0),
        ("v/b", "v/c", 1.0),
        ("v/c", "v/a", 1.0),
        ("v/c", "v/d", 1.0),
    ]


def test_train_embeddings_is_deterministic_for_same_seed() -> None:
    svc = Node2VecEmbeddingService(db=None, edge_collection="e")  # db unused for pure train
    params = Node2VecParams(dimensions=8, walk_length=8, num_walks=5, window_size=3, seed=123)
    emb1 = svc.train_embeddings(_toy_edges(), params)
    emb2 = svc.train_embeddings(_toy_edges(), params)

    assert emb1.keys() == emb2.keys()
    for k in emb1:
        assert np.allclose(np.array(emb1[k]), np.array(emb2[k]), atol=1e-8)


def test_train_embeddings_changes_with_different_seed() -> None:
    svc = Node2VecEmbeddingService(db=None, edge_collection="e")
    e = _toy_edges()
    emb1 = svc.train_embeddings(e, Node2VecParams(dimensions=8, walk_length=8, num_walks=5, window_size=3, seed=1))
    emb2 = svc.train_embeddings(e, Node2VecParams(dimensions=8, walk_length=8, num_walks=5, window_size=3, seed=2))

    # At least one node vector should differ
    diffs = []
    for k in emb1:
        diffs.append(not np.allclose(np.array(emb1[k]), np.array(emb2[k]), atol=1e-8))
    assert any(diffs)


def test_embedding_dimensions_and_normalization() -> None:
    svc = Node2VecEmbeddingService(db=None, edge_collection="e")
    params = Node2VecParams(dimensions=6, walk_length=6, num_walks=4, window_size=2, seed=42)
    emb = svc.train_embeddings(_toy_edges(), params)

    assert set(emb.keys()) == {"v/a", "v/b", "v/c", "v/d"}
    for vec in emb.values():
        assert len(vec) == 4  # dim is min(dimensions, num_nodes)
        norm = float(np.linalg.norm(np.array(vec)))
        # Either normalized or zero vector (should be normalized here)
        assert abs(norm - 1.0) < 1e-6


def test_empty_edges_returns_empty_embeddings() -> None:
    svc = Node2VecEmbeddingService(db=None, edge_collection="e")
    emb = svc.train_embeddings([], Node2VecParams())
    assert emb == {}


def test_train_embeddings_enforces_max_nodes_limit() -> None:
    # Create a chain of 4 nodes (exceeds max_nodes=3)
    edges = [("v/1", "v/2", 1.0), ("v/2", "v/3", 1.0), ("v/3", "v/4", 1.0)]
    svc = Node2VecEmbeddingService(db=None, edge_collection="e", safety_limits={"max_nodes": 3, "warn_nodes_threshold": 2})
    params = Node2VecParams(dimensions=4, walk_length=4, num_walks=2, window_size=2, seed=1)

    try:
        svc.train_embeddings(edges, params)
        assert False, "Expected ValueError for max_nodes safety limit"
    except ValueError as e:
        assert "max_nodes" in str(e)


def test_train_embeddings_enforces_max_dimensions_limit() -> None:
    svc = Node2VecEmbeddingService(db=None, edge_collection="e", safety_limits={"max_dimensions": 3})
    params = Node2VecParams(dimensions=4, walk_length=4, num_walks=2, window_size=2, seed=1)
    try:
        svc.train_embeddings(_toy_edges(), params)
        assert False, "Expected ValueError for max_dimensions safety limit"
    except ValueError as e:
        assert "max_dimensions" in str(e)


def test_fetch_edges_caps_unbounded_limit_and_enforces_max_edges_fetched() -> None:
    class _FakeAQL:
        def execute(self, query, bind_vars=None):
            # Return 3 edges regardless of limit clause
            return [
                {"_from": "v/a", "_to": "v/b", "w": 1.0},
                {"_from": "v/b", "_to": "v/c", "w": 1.0},
                {"_from": "v/c", "_to": "v/d", "w": 1.0},
            ]

    class _FakeDB:
        def __init__(self):
            self.aql = _FakeAQL()

        def has_collection(self, name: str) -> bool:
            return True

    svc = Node2VecEmbeddingService(
        db=_FakeDB(),
        edge_collection="e",
        safety_limits={"max_edges_fetched": 2, "warn_edges_threshold": 1},
    )

    try:
        svc.fetch_edges(limit=0)
        assert False, "Expected ValueError for max_edges_fetched safety limit"
    except ValueError as e:
        assert "max_edges_fetched" in str(e)

