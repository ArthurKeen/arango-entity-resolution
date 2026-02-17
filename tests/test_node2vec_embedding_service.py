from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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


def test_init_rejects_invalid_edge_collection_name() -> None:
    try:
        Node2VecEmbeddingService(db=None, edge_collection="bad-name")
        assert False, "Expected ValueError for invalid edge_collection name"
    except ValueError as e:
        assert "collection name" in str(e).lower()


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


def test_fetch_edges_happy_path_applies_filters_and_weights() -> None:
    class _FakeAQL:
        def __init__(self) -> None:
            self.last_query: Optional[str] = None
            self.last_bind_vars: Optional[Dict[str, Any]] = None

        def execute(self, query, bind_vars=None):
            self.last_query = str(query)
            self.last_bind_vars = dict(bind_vars or {})
            return [
                {"_from": "v/a", "_to": "v/b", "w": 0.95},
                {"_from": "v/b", "_to": "v/c", "w": 1.0},
                {"_from": "v/c", "_to": "v/d"},  # missing w -> default 1.0
            ]

    class _FakeDB:
        def __init__(self):
            self.aql = _FakeAQL()

        def has_collection(self, name: str) -> bool:
            return name == "e"

    db = _FakeDB()
    svc = Node2VecEmbeddingService(db=db, edge_collection="e", safety_limits={"max_edges_fetched": 10, "warn_edges_threshold": 0})

    edges = svc.fetch_edges(limit=3, min_confidence=0.9, method="cosine")
    assert edges == [
        ("v/a", "v/b", 0.95),
        ("v/b", "v/c", 1.0),
        ("v/c", "v/d", 1.0),
    ]

    assert db.aql.last_query is not None
    assert "FILTER e.method == @method" in db.aql.last_query
    assert "e.confidence != null AND e.confidence >= @min_confidence" in db.aql.last_query
    assert "LIMIT @limit" in db.aql.last_query
    assert db.aql.last_bind_vars == {"method": "cosine", "min_confidence": 0.9, "limit": 3}


def test_train_embeddings_rejects_invalid_params() -> None:
    svc = Node2VecEmbeddingService(db=None, edge_collection="e")

    for bad in [
        Node2VecParams(dimensions=0),
        Node2VecParams(walk_length=0),
        Node2VecParams(num_walks=0),
        Node2VecParams(window_size=0),
    ]:
        try:
            svc.train_embeddings(_toy_edges(), bad)
            assert False, f"Expected ValueError for invalid params: {bad}"
        except ValueError:
            pass


def test_train_embeddings_returns_zero_vectors_when_walk_length_is_one() -> None:
    # walk_length=1 produces walks with only the center node, so co-occurrence is all zeros.
    svc = Node2VecEmbeddingService(db=None, edge_collection="e")
    params = Node2VecParams(dimensions=8, walk_length=1, num_walks=3, window_size=2, seed=123)
    emb = svc.train_embeddings(_toy_edges(), params)

    assert set(emb.keys()) == {"v/a", "v/b", "v/c", "v/d"}
    for vec in emb.values():
        # dim is min(dimensions, num_nodes) == 4
        assert vec == [0.0, 0.0, 0.0, 0.0]


def test_write_embeddings_happy_path_groups_by_collection_and_batches() -> None:
    class _FakeCollection:
        def __init__(self) -> None:
            self.update_calls: List[Dict[str, Any]] = []

        def update_many(self, docs, silent: bool = True, merge: bool = True):
            self.update_calls.append({"docs": list(docs), "silent": silent, "merge": merge})

    class _FakeDB:
        def __init__(self) -> None:
            self._colls: Dict[str, _FakeCollection] = {"v": _FakeCollection(), "other": _FakeCollection()}

        def has_collection(self, name: str) -> bool:
            return name in self._colls

        def collection(self, name: str) -> _FakeCollection:
            return self._colls[name]

    db = _FakeDB()
    svc = Node2VecEmbeddingService(db=db, edge_collection="e")
    embeddings = {
        "v/a": [0.1, 0.2],
        "v/b": [0.3, 0.4],
        "v/c": [0.5, 0.6],
        "other/x": [0.7, 0.8],
    }
    params = Node2VecParams(dimensions=2, walk_length=2, num_walks=2, window_size=2, seed=7)

    out = svc.write_embeddings(embeddings, params=params, batch_size=2)
    assert out["updated"] == 4
    assert out["collections"] == {"v": 3, "other": 1}

    # v should have two batches (2 + 1) and other one batch
    assert len(db._colls["v"].update_calls) == 2
    assert len(db._colls["other"].update_calls) == 1

    for call in db._colls["v"].update_calls + db._colls["other"].update_calls:
        assert call["silent"] is True
        assert call["merge"] is True
        for doc in call["docs"]:
            assert "_key" in doc
            assert "node_embedding" in doc
            assert "node_embedding_meta" in doc
            assert doc["node_embedding_meta"]["method"] == "node2vec_svd"
            assert doc["node_embedding_meta"]["seed"] == 7


def test_write_embeddings_rejects_invalid_node_id_without_vertex_collection() -> None:
    class _FakeDB:
        def has_collection(self, name: str) -> bool:
            return True

        def collection(self, name: str):
            class _FakeCollection:
                def update_many(self, docs, silent: bool = True, merge: bool = True):
                    return None

            return _FakeCollection()

    svc = Node2VecEmbeddingService(db=_FakeDB(), edge_collection="e", vertex_collection=None)
    try:
        svc.write_embeddings({"just_a_key": [0.1]}, params=Node2VecParams(), batch_size=1000)
        assert False, "Expected ValueError for invalid node id"
    except ValueError as e:
        assert "collection/key" in str(e)

