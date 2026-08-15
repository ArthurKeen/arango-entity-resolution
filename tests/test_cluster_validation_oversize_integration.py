"""Cluster validation must flag runaway transitive closure.

Weakly connected components take the transitive closure, so one spurious edge
bridging two otherwise-separate groups collapses both into a single cluster.
That is entity resolution's signature failure mode: expensive to reverse, and
easy to miss because the run reports success and the cluster count merely looks
lower than expected.

`validate_clusters()` checked overlapping clusters, minimum size and sample
edges — every failure mode except that one. These tests cover the gap.

Oversized clusters are FLAGGED, never dropped: the legacy ClusteringService
discarded them, which silently removes those records from the output entirely.
Surfacing the problem is right; deleting the evidence is not.
"""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.services.wcc_clustering_service import WCCClusteringService


@pytest.fixture
def cluster_fixture(db_connection):
    """A vertex collection, similarity edges, and a cluster collection."""
    suffix = uuid.uuid4().hex[:8]
    vertices = f"cv_{suffix}"
    edges = f"ce_{suffix}"
    clusters = f"cc_{suffix}"
    db = db_connection

    db.create_collection(vertices)
    db.create_collection(edges, edge=True)
    db.create_collection(clusters)

    yield db, vertices, edges, clusters

    for name in (vertices, edges, clusters):
        if db.has_collection(name):
            db.delete_collection(name)


def _service(db, vertices, edges, clusters, min_cluster_size=2):
    return WCCClusteringService(
        db=db,
        edge_collection=edges,
        vertex_collection=vertices,
        cluster_collection=clusters,
        min_cluster_size=min_cluster_size,
    )


def _chain(db, vertices, edges, count):
    """A chain of `count` records — every pair transitively connected."""
    db.collection(vertices).insert_many(
        [{"_key": f"n{i}"} for i in range(count)]
    )
    db.collection(edges).insert_many([
        {
            "_from": f"{vertices}/n{i}",
            "_to": f"{vertices}/n{i + 1}",
            "similarity": 0.9,
        }
        for i in range(count - 1)
    ])


def test_oversized_cluster_is_flagged(cluster_fixture):
    """The regression this file exists for."""
    db, vertices, edges, clusters = cluster_fixture
    _chain(db, vertices, edges, 12)
    service = _service(db, vertices, edges, clusters)
    service.cluster(store_results=True)

    report = service.validate_clusters(max_cluster_size=5)

    oversized = [i for i in report["issues"] if i["type"] == "above_max_size"]
    assert oversized, (
        "a 12-member cluster against a limit of 5 was not flagged; runaway "
        f"transitive closure would go unnoticed. issues={report['issues']}"
    )
    assert oversized[0]["size"] == 12
    assert oversized[0]["max_allowed"] == 5
    assert "max_size_requirement" in report["checks_performed"]


def test_oversized_cluster_is_flagged_not_dropped(cluster_fixture):
    """Flagging must not delete the cluster — that would hide the evidence."""
    db, vertices, edges, clusters = cluster_fixture
    _chain(db, vertices, edges, 12)
    service = _service(db, vertices, edges, clusters)
    produced = service.cluster(store_results=True)

    assert len(produced) == 1 and len(produced[0]) == 12
    service.validate_clusters(max_cluster_size=5)

    stored = list(db.collection(clusters).all())
    assert len(stored) == 1, "validation must not remove the offending cluster"
    assert stored[0]["size"] == 12


def test_cluster_within_limit_is_not_flagged(cluster_fixture):
    db, vertices, edges, clusters = cluster_fixture
    _chain(db, vertices, edges, 4)
    service = _service(db, vertices, edges, clusters)
    service.cluster(store_results=True)

    report = service.validate_clusters(max_cluster_size=10)
    assert [i for i in report["issues"] if i["type"] == "above_max_size"] == []


def test_one_bridging_edge_creates_the_giant_cluster(cluster_fixture):
    """Demonstrates the mechanism the check exists to catch.

    Two clean groups of five stay separate until a single edge joins them, at
    which point transitive closure merges all ten — with nothing about the run
    itself indicating a problem.
    """
    db, vertices, edges, clusters = cluster_fixture
    db.collection(vertices).insert_many([{"_key": f"a{i}"} for i in range(5)])
    db.collection(vertices).insert_many([{"_key": f"b{i}"} for i in range(5)])
    db.collection(edges).insert_many(
        [{"_from": f"{vertices}/a{i}", "_to": f"{vertices}/a{i+1}", "similarity": 0.95}
         for i in range(4)]
        + [{"_from": f"{vertices}/b{i}", "_to": f"{vertices}/b{i+1}", "similarity": 0.95}
           for i in range(4)]
    )

    service = _service(db, vertices, edges, clusters)
    assert sorted(len(c) for c in service.cluster(store_results=True)) == [5, 5]

    # One weak, spurious edge bridges the two groups.
    db.collection(edges).insert(
        {"_from": f"{vertices}/a0", "_to": f"{vertices}/b0", "similarity": 0.51}
    )
    merged = service.cluster(store_results=True)
    assert [len(c) for c in merged] == [10], "closure should collapse both groups"

    report = service.validate_clusters(max_cluster_size=6)
    assert any(i["type"] == "above_max_size" for i in report["issues"])


def test_suppressing_the_bridge_restores_separate_clusters(cluster_fixture):
    """An analyst rejecting the bridging pair must undo the collapse."""
    db, vertices, edges, clusters = cluster_fixture
    db.collection(vertices).insert_many([{"_key": f"a{i}"} for i in range(3)])
    db.collection(vertices).insert_many([{"_key": f"b{i}"} for i in range(3)])
    db.collection(edges).insert_many([
        {"_from": f"{vertices}/a0", "_to": f"{vertices}/a1", "similarity": 0.95},
        {"_from": f"{vertices}/a1", "_to": f"{vertices}/a2", "similarity": 0.95},
        {"_from": f"{vertices}/b0", "_to": f"{vertices}/b1", "similarity": 0.95},
        {"_from": f"{vertices}/b1", "_to": f"{vertices}/b2", "similarity": 0.95},
    ])
    bridge = db.collection(edges).insert(
        {"_from": f"{vertices}/a0", "_to": f"{vertices}/b0", "similarity": 0.51}
    )

    service = _service(db, vertices, edges, clusters)
    assert [len(c) for c in service.cluster(store_results=True)] == [6]

    db.collection(edges).update({"_key": bridge["_key"], "suppressed": True})
    assert sorted(len(c) for c in service.cluster(store_results=True)) == [3, 3]


def test_default_limit_is_used_when_none_supplied(cluster_fixture):
    """Callers that pass nothing still get the check, not a silent skip."""
    db, vertices, edges, clusters = cluster_fixture
    _chain(db, vertices, edges, 4)
    service = _service(db, vertices, edges, clusters)
    service.cluster(store_results=True)

    report = service.validate_clusters()
    assert "max_size_requirement" in report["checks_performed"]
