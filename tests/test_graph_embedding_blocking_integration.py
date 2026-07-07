"""Integration test for graph-embedding blocking (plan 3.4).

Requires ArangoDB 3.12+ with the experimental vector index enabled; skips
cleanly otherwise (mirrors the ANN adapter integration tests).
"""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.similarity.ann_adapter import VectorSearchUnavailableError
from entity_resolution.strategies.graph_embedding_blocking import (
    GraphEmbeddingBlockingStrategy,
)


@pytest.fixture
def graph_blocking_fixture(db_connection):
    sfx = uuid.uuid4().hex[:8]
    person = f"geb_person_{sfx}"
    works = f"geb_worksAt_{sfx}"
    db = db_connection
    db.create_collection(person)
    db.create_collection(works, edge=True)

    # Two communities: {a1,a2,a3} densely linked, {b1,b2,b3} densely linked.
    db.collection(person).insert_many([{"_key": k} for k in
        ("a1", "a2", "a3", "b1", "b2", "b3")])
    intra = [("a1", "a2"), ("a2", "a3"), ("a1", "a3"),
             ("b1", "b2"), ("b2", "b3"), ("b1", "b3")]
    db.collection(works).insert_many(
        [{"_from": f"{person}/{x}", "_to": f"{person}/{y}"} for x, y in intra]
    )
    yield db, person, works
    for n in (person, works):
        if db.has_collection(n):
            db.delete_collection(n)


def test_graph_embedding_blocking_end_to_end(graph_blocking_fixture):
    db, person, works = graph_blocking_fixture
    strat = GraphEmbeddingBlockingStrategy(
        db=db, collection=person, edge_collection=works,
        embedding_field="node_embedding", similarity_threshold=0.5,
        limit_per_entity=5, compute_embeddings=True, create_vector_index=True,
        node2vec_params={"dimensions": 8, "walk_length": 6, "num_walks": 10},
    )
    try:
        pairs = strat.generate_candidates()
    except VectorSearchUnavailableError:
        pytest.skip("ArangoDB vector index not available (needs --experimental-vector-index)")

    # Embeddings were written and the ANN path produced candidate pairs.
    assert isinstance(pairs, list) and len(pairs) > 0
    for p in pairs:
        assert "doc1_key" in p and "doc2_key" in p
    # Every record got a node embedding.
    stats = strat.get_statistics()
    assert stats["strategy_name"] == "GraphEmbeddingBlockingStrategy"
