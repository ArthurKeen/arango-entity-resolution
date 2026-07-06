"""Integration tests for incremental cluster maintenance (plan 3.3)."""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.core.incremental_maintainer import IncrementalMaintainer
from entity_resolution.services.feedback_application_service import FeedbackApplicationService


@pytest.fixture
def maint_fixture(db_connection):
    suffix = uuid.uuid4().hex[:8]
    person = f"im_person_{suffix}"
    edge = f"im_edge_{suffix}"
    cluster = f"im_cluster_{suffix}"
    db = db_connection
    db.create_collection(person)
    db.create_collection(edge, edge=True)
    db.create_collection(cluster)
    yield db, person, edge, cluster
    for n in (person, edge, cluster):
        if db.has_collection(n):
            db.delete_collection(n)


def _maintainer(db, person, edge, cluster):
    return IncrementalMaintainer(
        db=db, collection=person, fields=["name"],
        edge_collection=edge, cluster_collection=cluster,
        confidence_threshold=0.8, blocking_strategy="full",
    )


def _member_sets(db, cluster):
    return sorted(
        tuple(sorted(c["member_keys"])) for c in db.collection(cluster).all()
    )


def test_commit_merges_matching_records(maint_fixture):
    db, person, edge, cluster = maint_fixture
    db.collection(person).insert_many([
        {"_key": "a", "name": "Acme Corporation"},
        {"_key": "b", "name": "Acme Corporatn"},
    ])
    m = _maintainer(db, person, edge, cluster)
    m.resolve_and_commit("a")
    m.resolve_and_commit("b")
    assert _member_sets(db, cluster) == [("a", "b")]
    # Records are stamped so a watcher won't reprocess them.
    assert m.pending_keys() == []


def test_sequence_neutral(db_connection):
    # Same records, two insertion/commit orders => identical final clusters.
    def run(order):
        sfx = uuid.uuid4().hex[:8]
        person, edge, cluster = f"sn_p_{sfx}", f"sn_e_{sfx}", f"sn_c_{sfx}"
        db_connection.create_collection(person)
        db_connection.create_collection(edge, edge=True)
        db_connection.create_collection(cluster)
        try:
            db_connection.collection(person).insert_many([
                {"_key": "a", "name": "Globex Company"},
                {"_key": "b", "name": "Globex Compny"},
                {"_key": "c", "name": "Globex Comany"},
            ])
            m = IncrementalMaintainer(
                db=db_connection, collection=person, fields=["name"],
                edge_collection=edge, cluster_collection=cluster,
                confidence_threshold=0.8, blocking_strategy="full",
            )
            for k in order:
                m.resolve_and_commit(k)
            return sorted(tuple(sorted(c["member_keys"])) for c in db_connection.collection(cluster).all())
        finally:
            for n in (person, edge, cluster):
                if db_connection.has_collection(n):
                    db_connection.delete_collection(n)

    assert run(["a", "b", "c"]) == run(["c", "b", "a"])


def test_suppressed_edge_not_resurrected(maint_fixture):
    db, person, edge, cluster = maint_fixture
    db.collection(person).insert_many([
        {"_key": "a", "name": "Initech LLC"},
        {"_key": "b", "name": "Initech LLC"},
    ])
    # A human already decided a and b are NOT a match.
    FeedbackApplicationService(
        db=db, edge_collection=edge, vertex_collection=person, cluster_collection=cluster,
    ).apply_verdict("a", "b", "no_match", actor="steward")

    m = _maintainer(db, person, edge, cluster)
    m.resolve_and_commit("b")

    # The suppression must hold: no cluster contains both a and b.
    for members in _member_sets(db, cluster):
        assert not ({"a", "b"} <= set(members))
