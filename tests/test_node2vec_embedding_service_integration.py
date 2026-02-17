from __future__ import annotations

import uuid
from typing import Any, Dict, List

import pytest

from entity_resolution.services.node2vec_embedding_service import Node2VecEmbeddingService, Node2VecParams


def _create_vertex_and_edge_collections(db) -> Dict[str, str]:
    vcol = f"test_node2vec_v_{uuid.uuid4().hex[:10]}"
    ecol = f"test_node2vec_e_{uuid.uuid4().hex[:10]}"

    if db.has_collection(vcol):
        db.delete_collection(vcol)
    if db.has_collection(ecol):
        db.delete_collection(ecol)

    db.create_collection(vcol)
    db.create_collection(ecol, edge=True)
    return {"vcol": vcol, "ecol": ecol}


def _drop_if_exists(db, name: str) -> None:
    if db.has_collection(name):
        db.delete_collection(name)


@pytest.mark.integration
def test_node2vec_fetch_train_write_roundtrip_with_real_arango(db_connection) -> None:
    names = _create_vertex_and_edge_collections(db_connection)
    vcol, ecol = names["vcol"], names["ecol"]

    try:
        v = db_connection.collection(vcol)
        e = db_connection.collection(ecol)

        # Insert 4 vertices
        v.insert_many([{"_key": "a"}, {"_key": "b"}, {"_key": "c"}, {"_key": "d"}])

        # Insert edges with method + confidence
        e.insert_many(
            [
                {"_from": f"{vcol}/a", "_to": f"{vcol}/b", "method": "cosine", "confidence": 0.95},
                {"_from": f"{vcol}/b", "_to": f"{vcol}/c", "method": "cosine", "confidence": 0.50},
                {"_from": f"{vcol}/c", "_to": f"{vcol}/d", "method": "cosine"},  # no confidence -> weight=1.0
                {"_from": f"{vcol}/a", "_to": f"{vcol}/d", "method": "other", "confidence": 0.99},
            ]
        )

        svc = Node2VecEmbeddingService(db=db_connection, edge_collection=ecol)

        # Happy-path fetch: method filter should exclude "other"
        edges = svc.fetch_edges(limit=100, method="cosine")
        assert set(edges) == {
            (f"{vcol}/a", f"{vcol}/b", 0.95),
            (f"{vcol}/b", f"{vcol}/c", 0.50),
            (f"{vcol}/c", f"{vcol}/d", 1.0),
        }

        params = Node2VecParams(dimensions=8, walk_length=6, num_walks=3, window_size=2, seed=123)
        embeddings = svc.train_embeddings(edges, params)
        assert set(embeddings.keys()) == {f"{vcol}/a", f"{vcol}/b", f"{vcol}/c", f"{vcol}/d"}

        out = svc.write_embeddings(embeddings, params=params, batch_size=2)
        assert out["updated"] == 4
        assert out["collections"] == {vcol: 4}

        # Verify vertex documents were updated with embeddings + metadata
        for k in ["a", "b", "c", "d"]:
            doc = v.get(k)
            assert doc is not None
            assert "node_embedding" in doc
            assert "node_embedding_meta" in doc
            vec = doc["node_embedding"]
            meta = doc["node_embedding_meta"]
            assert isinstance(vec, list)
            assert len(vec) == 4  # dim is min(dimensions, num_nodes)
            assert meta["method"] == "node2vec_svd"
            assert meta["seed"] == 123

    finally:
        _drop_if_exists(db_connection, ecol)
        _drop_if_exists(db_connection, vcol)


@pytest.mark.integration
def test_node2vec_write_embeddings_accepts_keys_when_vertex_collection_is_set(db_connection) -> None:
    names = _create_vertex_and_edge_collections(db_connection)
    vcol, ecol = names["vcol"], names["ecol"]

    try:
        v = db_connection.collection(vcol)
        v.insert_many([{"_key": "a"}, {"_key": "b"}])

        svc = Node2VecEmbeddingService(db=db_connection, edge_collection=ecol, vertex_collection=vcol)
        params = Node2VecParams(dimensions=2, walk_length=2, num_walks=2, window_size=2, seed=7)

        # Keys-only embeddings (no "collection/key")
        out = svc.write_embeddings({"a": [0.1, 0.2], "b": [0.3, 0.4]}, params=params, batch_size=1000)
        assert out["updated"] == 2
        assert out["collections"] == {vcol: 2}

        doc_a = v.get("a")
        assert doc_a is not None
        assert doc_a["node_embedding"] == [0.1, 0.2]
        assert doc_a["node_embedding_meta"]["seed"] == 7

    finally:
        _drop_if_exists(db_connection, ecol)
        _drop_if_exists(db_connection, vcol)

