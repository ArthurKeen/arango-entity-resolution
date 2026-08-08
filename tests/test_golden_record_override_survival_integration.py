"""Steward golden-record corrections must survive a pipeline rerun.

`GoldenRecordPersistenceService` recomputes every consolidated field on each run
and merges the result over the stored record (`overwrite_mode="update"`). Before
`fieldOverrides` existed, that silently reverted every manual correction — and
because `editedBy` is not recomputed it survived the merge, leaving a record that
claimed a human authored values the pipeline had actually produced. A wrong value
presented as analyst-verified is worse than an obviously machine-generated one.

Pairwise adjudication already got this right (verdicts live on edges as
suppressed/confirmed and re-clustering honours them); these tests hold the golden
record path to the same standard.

Live-database tests: the behaviour under test *is* the persistence semantics, and
a fake cannot demonstrate what ArangoDB's update-mode merge actually does.
"""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.services.golden_record_persistence_service import (
    GoldenRecordPersistenceService,
)


@pytest.fixture
def golden_fixture(db_connection):
    """Two records forming one cluster, disagreeing on a field."""
    suffix = uuid.uuid4().hex[:8]
    source = f"gro_person_{suffix}"
    clusters = f"gro_clusters_{suffix}"
    golden = f"gro_golden_{suffix}"
    edges = f"gro_resolved_{suffix}"
    db = db_connection

    db.create_collection(source)
    db.create_collection(clusters)
    db.collection(source).insert_many([
        # 'name' disagrees 2-to-1, so field_voting picks "Jon Smith".
        {"_key": "r1", "name": "Jon Smith", "city": "Boston"},
        {"_key": "r2", "name": "Jon Smith", "city": "Boston"},
        {"_key": "r3", "name": "Jonathan Smith", "city": "Boston"},
    ])
    db.collection(clusters).insert({
        "_key": "c1",
        "cluster_id": "c1",
        "members": [f"{source}/r1", f"{source}/r2", f"{source}/r3"],
    })

    yield db, source, clusters, golden, edges

    for name in (source, clusters, golden, edges):
        if db.has_collection(name):
            db.delete_collection(name)


def _service(db, source, clusters, golden, edges):
    return GoldenRecordPersistenceService(
        db=db,
        source_collection=source,
        cluster_collection=clusters,
        golden_collection=golden,
        resolved_edge_collection=edges,
        merge_strategy="field_voting",
        include_provenance=True,
    )


def test_machine_consolidation_picks_the_majority_value(golden_fixture):
    """Baseline: without any override, field voting wins."""
    db, source, clusters, golden, edges = golden_fixture
    _service(db, source, clusters, golden, edges).run()

    docs = list(db.collection(golden).all())
    assert len(docs) == 1
    assert docs[0]["name"] == "Jon Smith"


def test_steward_override_survives_a_rerun(golden_fixture):
    """The regression this file exists for."""
    db, source, clusters, golden, edges = golden_fixture
    service = _service(db, source, clusters, golden, edges)
    service.run()

    doc = list(db.collection(golden).all())[0]
    key = doc["_key"]

    # A steward decides the formal name is correct, as the UI apply route writes
    # it: the flat value for readers, plus the override that must outlive reruns.
    db.collection(golden).update({
        "_key": key,
        "name": "Jonathan Smith",
        "fieldOverrides": {"name": "Jonathan Smith"},
        "editedBy": "analyst@example.com",
        "method": "manual_edit",
    })

    service.run()  # pipeline runs again over unchanged source data

    after = db.collection(golden).get(key)
    assert after["name"] == "Jonathan Smith", (
        "the steward's correction was reverted to the machine's choice; a rerun "
        "must not silently discard human adjudication"
    )
    assert after["editedBy"] == "analyst@example.com"
    assert after["fieldOverrides"]["name"] == "Jonathan Smith"


def test_override_is_marked_as_such_in_provenance(golden_fixture):
    """Provenance must not attribute an override to a survivorship strategy."""
    db, source, clusters, golden, edges = golden_fixture
    service = _service(db, source, clusters, golden, edges)
    service.run()
    key = list(db.collection(golden).all())[0]["_key"]

    db.collection(golden).update({
        "_key": key,
        "name": "Jonathan Smith",
        "fieldOverrides": {"name": "Jonathan Smith"},
    })
    service.run()

    provenance = db.collection(golden).get(key)["fieldProvenance"]
    assert provenance["name"]["strategy"] == "manual_override"
    assert provenance["name"]["chosenFrom"] == "steward"
    # Untouched fields keep their computed provenance.
    assert provenance["city"]["strategy"] == "field_voting"


def test_non_overridden_fields_still_recompute(golden_fixture):
    """Overrides must pin only what a steward actually changed."""
    db, source, clusters, golden, edges = golden_fixture
    service = _service(db, source, clusters, golden, edges)
    service.run()
    key = list(db.collection(golden).all())[0]["_key"]

    db.collection(golden).update({
        "_key": key,
        "fieldOverrides": {"name": "Jonathan Smith"},
    })
    # Source data changes for a field the steward did not touch.
    db.collection(source).update({"_key": "r1", "city": "Cambridge"})
    db.collection(source).update({"_key": "r2", "city": "Cambridge"})
    service.run()

    after = db.collection(golden).get(key)
    assert after["name"] == "Jonathan Smith", "override still pinned"
    assert after["city"] == "Cambridge", (
        "a field with no override must track the source data"
    )


def test_reserved_keys_in_overrides_are_ignored(golden_fixture):
    """An override must not be able to rewrite system metadata."""
    db, source, clusters, golden, edges = golden_fixture
    service = _service(db, source, clusters, golden, edges)
    service.run()
    key = list(db.collection(golden).all())[0]["_key"]

    db.collection(golden).update({
        "_key": key,
        "fieldOverrides": {"_key": "hijacked", "clusterSize": 999,
                           "name": "Jonathan Smith"},
    })
    service.run()

    after = db.collection(golden).get(key)
    assert after["_key"] == key
    assert after["clusterSize"] == 3, "system field must not be overridable"
    assert after["name"] == "Jonathan Smith", "ordinary field still applies"


def test_malformed_overrides_do_not_break_the_run(golden_fixture):
    """A non-dict fieldOverrides must be ignored, not raise."""
    db, source, clusters, golden, edges = golden_fixture
    service = _service(db, source, clusters, golden, edges)
    service.run()
    key = list(db.collection(golden).all())[0]["_key"]

    db.collection(golden).update({"_key": key, "fieldOverrides": "not-a-dict"})
    service.run()

    assert db.collection(golden).get(key)["name"] == "Jon Smith"


def test_source_field_cannot_clobber_golden_metadata(golden_fixture):
    """A source column named like golden metadata must not corrupt the record.

    Consolidated values used to be spread last into the golden document, so a
    source field named `method`, `stale` or `clusterSize` overwrote the record's
    own metadata. Those are plausible real column names — overwriting `method`
    breaks manual-edit detection, and overwriting `sourceClusterHash`/`stale`
    breaks staleness detection.
    """
    db, source, clusters, golden, edges = golden_fixture
    for key in ("r1", "r2", "r3"):
        db.collection(source).update({
            "_key": key,
            "method": "credit_card",     # a real business field
            "stale": "whatever",
            "clusterSize": 12345,
        })

    _service(db, source, clusters, golden, edges).run()

    doc = list(db.collection(golden).all())[0]
    assert doc["method"] == "golden_record_persistence", (
        "a source 'method' column overwrote golden-record metadata"
    )
    assert doc["stale"] is False
    assert doc["clusterSize"] == 3
    # Ordinary fields are still consolidated normally.
    assert doc["city"] == "Boston"
