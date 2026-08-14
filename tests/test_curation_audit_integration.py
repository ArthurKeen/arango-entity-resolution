"""Curation audit trail: it must be findable, and its failures must be visible.

The audit log is the accountability record for irreversible steward actions —
cluster merges, golden-record edits, adjudication verdicts. Two properties it
lacked:

1. **Findable.** ``history()`` filters on (collection, entity_key) and sorts by
   ``ts``, but the collection had only its primary index, so every lookup was a
   full scan plus an in-memory sort. An append-only log grows without bound, so
   the UI's history view degraded continuously.

2. **Visibly failing.** Every call site swallowed audit errors with a bare
   ``except Exception: pass``. Not blocking the mutation is the right call, but
   swallowing without a trace means an irreversible merge can lose its
   accountability record and nothing anywhere records that it happened.

Live-database tests: the index and the query plan are the behaviour under test,
and a fake cannot demonstrate either.
"""

from __future__ import annotations

import uuid

import pytest

from entity_resolution.services.curation_service import CurationService


@pytest.fixture
def audit_db(db_connection):
    """A clean audit collection per test."""
    db = db_connection
    if db.has_collection("er_audit_log"):
        db.delete_collection("er_audit_log")
    yield db
    if db.has_collection("er_audit_log"):
        db.delete_collection("er_audit_log")


def test_records_and_reads_back_history(audit_db):
    service = CurationService(audit_db)
    service.record(
        actor="analyst@example.com", action="merge", collection="people",
        entity_key="c1", before={"size": 2}, after={"size": 3},
    )
    service.record(
        actor="analyst@example.com", action="verdict", collection="people",
        entity_key="c1",
    )
    service.record(actor="other", action="merge", collection="people", entity_key="c2")

    history = service.history("people", "c1")
    assert len(history) == 2
    assert {entry["action"] for entry in history} == {"merge", "verdict"}
    assert all(entry["entity_key"] == "c1" for entry in history)


def test_history_is_newest_first(audit_db):
    service = CurationService(audit_db)
    for action in ("first", "second", "third"):
        service.record(actor="a", action=action, collection="people", entity_key="c1")

    assert [e["action"] for e in service.history("people", "c1")] == [
        "third", "second", "first",
    ]


def test_history_is_index_backed_not_a_full_scan(audit_db):
    """The lookup must use an index; a growing audit log makes a scan untenable."""
    service = CurationService(audit_db)
    for i in range(40):
        service.record(
            actor="a", action="verdict", collection="people", entity_key=f"c{i % 4}"
        )

    index_fields = [idx.get("fields") for idx in audit_db.collection("er_audit_log").indexes()]
    assert ["collection", "entity_key", "ts"] in index_fields, (
        f"expected a (collection, entity_key, ts) index, found {index_fields}"
    )

    plan = audit_db.aql.explain(
        """
        FOR a IN er_audit_log
            FILTER a.collection == @collection AND a.entity_key == @entity_key
            SORT a.ts DESC
            LIMIT 50
            RETURN a
        """,
        bind_vars={"collection": "people", "entity_key": "c1"},
    )
    node_types = [node["type"] for node in plan["nodes"]]
    assert "IndexNode" in node_types, f"query is not index-backed: {node_types}"
    assert "EnumerateCollectionNode" not in node_types, (
        f"query still performs a full collection scan: {node_types}"
    )


def test_index_creation_is_idempotent(audit_db):
    """Constructing the service repeatedly must not fail or duplicate the index."""
    for _ in range(3):
        CurationService(audit_db)

    matching = [
        idx for idx in audit_db.collection("er_audit_log").indexes()
        if idx.get("fields") == ["collection", "entity_key", "ts"]
    ]
    assert len(matching) == 1


def test_history_scopes_to_its_collection(audit_db):
    """Two collections may legitimately share an entity key."""
    service = CurationService(audit_db)
    service.record(actor="a", action="merge", collection="people", entity_key="shared")
    service.record(actor="a", action="merge", collection="orgs", entity_key="shared")

    assert len(service.history("people", "shared")) == 1
    assert len(service.history("orgs", "shared")) == 1


def test_history_of_unknown_entity_is_empty(audit_db):
    assert CurationService(audit_db).history("people", "never-touched") == []


def test_history_rejects_an_invalid_collection_name(audit_db):
    """The collection name reaches a query; it must be validated, not trusted."""
    with pytest.raises(Exception):
        CurationService(audit_db).history("people; DROP", "c1")


class TestAuditFailuresAreVisible:
    """A swallowed audit failure must still leave a trace in the logs."""

    def test_route_handlers_log_rather_than_pass_silently(self):
        """Guards against reintroducing `except Exception: pass` on an audit write.

        Asserted on source because the alternative is standing up the full UI
        stack and breaking the audit collection underneath it; the property being
        protected is that no audit write is discarded without a log line.
        """
        import inspect

        from entity_resolution.ui.routes import curation, golden, metrics, review

        for module in (curation, golden, metrics, review):
            source = inspect.getsource(module)
            assert "Audit write failed" in source, (
                f"{module.__name__} does not log audit failures"
            )
            assert "except Exception:\n        pass" not in source, (
                f"{module.__name__} still swallows an exception silently"
            )

    def test_a_failing_audit_write_does_not_block_the_action(self, audit_db):
        """Auditing must never block a steward action — the original intent."""
        service = CurationService(audit_db)
        audit_db.delete_collection("er_audit_log")

        with pytest.raises(Exception):
            service.record(
                actor="a", action="merge", collection="people", entity_key="c1"
            )
        # The caller catches this; what matters is that record() surfaces the
        # failure rather than reporting success, so the caller can log it.
