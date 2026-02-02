from __future__ import annotations

import pytest

from entity_resolution.services.golden_record_persistence_service import GoldenRecordPersistenceService


@pytest.fixture
def db():
    class MockCollection:
        def __init__(self, name: str, edge: bool = False):
            self.name = name
            self.edge = edge
            self.docs_by_key = {}
            self.docs = []

        def get(self, key):
            return self.docs_by_key.get(key)

        def insert_many(self, docs, overwrite_mode=None):
            # Minimal overwrite semantics:
            # - update: merge by _key
            # - ignore: skip if exists
            for d in docs:
                k = d.get("_key")
                if k is None:
                    continue
                if overwrite_mode == "ignore" and k in self.docs_by_key:
                    continue
                if overwrite_mode == "update" and k in self.docs_by_key:
                    existing = dict(self.docs_by_key[k])
                    existing.update(d)
                    self.docs_by_key[k] = existing
                else:
                    self.docs_by_key[k] = dict(d)
            self.docs = list(self.docs_by_key.values())
            return len(docs)

        def __iter__(self):
            return iter(self.docs)

    class MockDB:
        def __init__(self):
            self._collections = {}

        def has_collection(self, name):
            return name in self._collections

        def create_collection(self, name, edge=False, system=False):
            self._collections[name] = MockCollection(name, edge=edge)
            return self._collections[name]

        def collection(self, name):
            return self._collections[name]

    db = MockDB()

    people = db.create_collection("Person")
    people.docs_by_key["p1"] = {"_key": "p1", "_id": "Person/p1", "name": "Alice", "panNumber": "AAAAA0000A"}
    people.docs_by_key["p2"] = {"_key": "p2", "_id": "Person/p2", "name": "Alice", "panNumber": "AAAAA0000A"}
    people.docs_by_key["p3"] = {"_key": "p3", "_id": "Person/p3", "name": "Bob", "panNumber": "BBBBB0000B"}

    clusters = db.create_collection("person_clusters")
    clusters.docs = [
        {"_key": "cluster_000001", "cluster_id": 1, "members": ["Person/p1", "Person/p2"], "member_keys": ["p1", "p2"]},
        {"_key": "cluster_000002", "cluster_id": 2, "members": ["Person/p3"], "member_keys": ["p3"]},
    ]

    return db


def test_persists_golden_records_and_resolvedto_edges(db):
    svc = GoldenRecordPersistenceService(
        db=db,
        source_collection="Person",
        cluster_collection="person_clusters",
        golden_collection="GoldenRecord",
        resolved_edge_collection="resolvedTo",
        include_fields=["name", "panNumber"],
        include_provenance=False,
    )
    out = svc.run(run_id="run-test", min_cluster_size=2)

    assert out["clusters_processed"] == 1
    assert out["golden_records_upserted"] == 1
    assert out["resolved_edges_upserted"] == 2

    golden = db.collection("GoldenRecord")
    assert len(golden.docs) == 1
    gr = golden.docs[0]
    assert gr["clusterSize"] == 2
    assert gr["name"] == "Alice"
    assert gr["panNumber"] == "AAAAA0000A"

    edges = db.collection("resolvedTo")
    assert len(edges.docs) == 2
    tos = {e["_to"] for e in edges.docs}
    assert len(tos) == 1


def test_idempotent_rerun_does_not_create_more_goldens_or_edges(db):
    svc = GoldenRecordPersistenceService(
        db=db,
        source_collection="Person",
        cluster_collection="person_clusters",
        golden_collection="GoldenRecord",
        resolved_edge_collection="resolvedTo",
        include_fields=["name", "panNumber"],
        include_provenance=False,
    )
    svc.run(run_id="run-test", min_cluster_size=2)
    svc.run(run_id="run-test-2", min_cluster_size=2)

    assert len(db.collection("GoldenRecord").docs) == 1
    assert len(db.collection("resolvedTo").docs) == 2

