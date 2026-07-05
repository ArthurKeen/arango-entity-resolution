"""Integration tests for GraphContextSimilarity against a real ArangoDB (plan 3.1)."""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.similarity.graph_context import GraphContextSimilarity
from entity_resolution.services.batch_similarity_service import BatchSimilarityService


@pytest.fixture
def graph_fixture(db_connection):
    suffix = uuid.uuid4().hex[:8]
    person = f"gcp_person_{suffix}"
    org = f"gcp_org_{suffix}"
    works = f"gcp_worksAt_{suffix}"
    db = db_connection
    db.create_collection(person)
    db.create_collection(org)
    db.create_collection(works, edge=True)

    db.collection(person).insert_many([
        {"_key": "a", "name": "Acme Analytics"},
        {"_key": "b", "name": "Acme Analytic"},
        {"_key": "c", "name": "Zeta Foods"},
    ])
    db.collection(org).insert_many([{"_key": "o1"}, {"_key": "o2"}])
    # a and b both work at o1 (shared employer); c works at o2.
    db.collection(works).insert_many([
        {"_from": f"{person}/a", "_to": f"{org}/o1"},
        {"_from": f"{person}/b", "_to": f"{org}/o1"},
        {"_from": f"{person}/c", "_to": f"{org}/o2"},
    ])

    yield db, person, works
    for n in (person, org, works):
        if db.has_collection(n):
            db.delete_collection(n)


def test_batch_neighbor_fetch_and_shared_employer(graph_fixture):
    db, person, works = graph_fixture
    svc = GraphContextSimilarity(db, person, [works], max_hops=2)

    cache = svc.batch_fetch_neighbor_sets(["a", "b", "c"])
    # a and b share the same employer hub; c links a different one.
    assert cache["a"] == cache["b"]
    assert cache["a"] and all("gcp_org" in n for n in cache["a"])
    assert cache["a"].isdisjoint(cache["c"])

    ab = svc.pair_features("a", "b", cache)
    assert ab["graph_neighbor_jaccard"] == pytest.approx(1.0)  # both only link o1
    assert ab["graph_shared_neighbor_count"] > 0
    assert ab["graph_path_within_k"] == 1.0

    ac = svc.pair_features("a", "c", cache)
    assert ac["graph_neighbor_jaccard"] == 0.0
    assert ac["graph_path_within_k"] == 0.0


def test_graph_features_flow_into_detailed_field_scores(graph_fixture):
    db, person, works = graph_fixture
    gc = GraphContextSimilarity(db, person, [works], max_hops=2)
    svc = BatchSimilarityService(
        db=db,
        collection=person,
        field_weights={"name": 1.0},
        graph_context=gc,
    )
    results = svc.compute_similarities_detailed([("a", "b")], threshold=0.0)
    assert len(results) == 1
    fs = results[0]["field_scores"]
    # Both the attribute field and the graph features are present in the vector.
    assert "name" in fs
    assert fs["graph_neighbor_jaccard"] == pytest.approx(1.0)
    assert fs["graph_path_within_k"] == 1.0


def test_graph_features_reach_fs_scoring(graph_fixture):
    db, person, works = graph_fixture
    gc = GraphContextSimilarity(db, person, [works], max_hops=2)

    seen: dict = {}

    class _FakeFS:
        def score(self, field_scores):
            seen.update(field_scores)
            return 0.9

    svc = BatchSimilarityService(
        db=db,
        collection=person,
        field_weights={"name": 1.0},
        scoring_method="fellegi_sunter",
        fs_scorer=_FakeFS(),
        graph_context=gc,
    )
    out = svc.compute_similarities([("a", "b")], threshold=0.0, return_all=True)
    assert out and out[0][2] == pytest.approx(0.9)
    # The FS scorer received the graph features in its comparison vector.
    assert seen.get("graph_neighbor_jaccard") == pytest.approx(1.0)
    assert seen.get("graph_path_within_k") == 1.0
