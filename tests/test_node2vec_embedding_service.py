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

