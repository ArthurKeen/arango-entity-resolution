"""Integration test for collective resolution against a real ArangoDB (plan 3.2).

Demonstrates the lift: a record with no employer edge is merged by name to a
peer, then inherits that peer's employer, which pulls in further same-employer
records that a single pass misses.
"""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.core.collective_resolver import CollectiveResolver, connected_components
from entity_resolution.services.batch_similarity_service import BatchSimilarityService
from entity_resolution.similarity.graph_context import GraphContextSimilarity


@pytest.fixture
def collective_fixture(db_connection):
    suffix = uuid.uuid4().hex[:8]
    person = f"col_person_{suffix}"
    org = f"col_org_{suffix}"
    works = f"col_worksAt_{suffix}"
    db = db_connection
    db.create_collection(person)
    db.create_collection(org)
    db.create_collection(works, edge=True)

    # A~B by name; B,C,D all work at o1; A has no employer edge.
    db.collection(person).insert_many([
        {"_key": "A", "name": "Globex Corporation"},
        {"_key": "B", "name": "Globex Corporatn"},
        {"_key": "C", "name": "Initech"},
        {"_key": "D", "name": "Umbrella"},
    ])
    db.collection(org).insert({"_key": "o1"})
    db.collection(works).insert_many([
        {"_from": f"{person}/B", "_to": f"{org}/o1"},
        {"_from": f"{person}/C", "_to": f"{org}/o1"},
        {"_from": f"{person}/D", "_to": f"{org}/o1"},
    ])
    yield db, person, works
    for n in (person, org, works):
        if db.has_collection(n):
            db.delete_collection(n)


class _MaxFS:
    """Toy FS scorer: match if the name agrees OR the pair shares a neighbour."""

    # Signature mirrors FellegiSunterScorer.score, including exact_values (used
    # for term-frequency adjustment). This double ignores it, but must still
    # accept it — a double that drifts from the real interface turns a genuine
    # break into a passing test.
    def score(self, field_scores, exact_values=None):
        return max(
            field_scores.get("name", 0.0),
            field_scores.get("graph_neighbor_jaccard", 0.0),
            field_scores.get("graph_path_within_k", 0.0),
        )


def _resolver(db, person, works, *, max_rounds):
    gc = GraphContextSimilarity(db, person, [works], max_hops=2)
    sim = BatchSimilarityService(
        db=db, collection=person, field_weights={"name": 1.0},
        scoring_method="fellegi_sunter", fs_scorer=_MaxFS(), graph_context=gc,
    )
    base = gc.batch_fetch_neighbor_sets(["A", "B", "C", "D"])

    def score_fn(pairs, cache):
        return sim.compute_similarities(list(pairs), threshold=0.0, return_all=True, neighbor_cache=cache)

    return CollectiveResolver(
        score_pairs=score_fn, cluster=connected_components,
        base_neighbor_cache=base, threshold=0.7, max_rounds=max_rounds,
    )


def test_single_pass_misses_transferred_relationship(collective_fixture):
    db, person, works = collective_fixture
    pairs = [("A", "B"), ("A", "C"), ("A", "D")]
    single = _resolver(db, person, works, max_rounds=1).resolve(pairs)
    # A~B by name only; A has no employer yet, so A~C / A~D don't fire.
    assert single["clusters"] == [["A", "B"]]


def test_collective_propagates_merge(collective_fixture):
    db, person, works = collective_fixture
    pairs = [("A", "B"), ("A", "C"), ("A", "D")]
    result = _resolver(db, person, works, max_rounds=5).resolve(pairs)
    assert result["converged"] is True
    assert result["clusters"] == [["A", "B", "C", "D"]]
    assert result["rounds"] >= 2
