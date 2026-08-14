"""Unit tests for the schema migration runner (plan 1.0)."""

from __future__ import annotations

import pytest

from entity_resolution.migrations import (
    MIGRATIONS,
    Migration,
    MigrationRunner,
    SchemaVersionError,
)


class _FakeCollection:
    def __init__(self, name):
        self.name = name
        self.docs = {}
        #: Index definitions applied, so migrations that add indexes are
        #: observable. This double must mirror the real collection interface:
        #: a double that lags behind it turns a genuine interface change into a
        #: confusing test failure, and a genuine break into a passing test.
        self.indexes_created = []

    def get(self, key):
        return self.docs.get(key)

    def insert(self, doc, overwrite=False):
        key = doc["_key"]
        if key in self.docs and not overwrite:
            raise Exception("duplicate")
        self.docs[key] = dict(doc)

    def add_persistent_index(self, fields, name=None, sparse=False, unique=False):
        definition = {
            "fields": list(fields), "name": name,
            "sparse": sparse, "unique": unique,
        }
        # ArangoDB treats an identical definition as a no-op, so migrations stay
        # idempotent; mirror that rather than accumulating duplicates.
        if definition not in self.indexes_created:
            self.indexes_created.append(definition)
        return definition


class _FakeDB:
    def __init__(self):
        self._collections = {}

    def has_collection(self, name):
        return name in self._collections

    def create_collection(self, name, edge=False):
        self._collections.setdefault(name, _FakeCollection(name))
        return self._collections[name]

    def collection(self, name):
        return self._collections[name]


def _runner(db, migrations=None):
    return MigrationRunner(db, migrations=migrations)


def test_fresh_db_starts_at_version_zero():
    assert _runner(_FakeDB()).current_version() == 0


def test_migrate_applies_baseline_and_records_version():
    db = _FakeDB()
    runner = _runner(db)
    out = runner.migrate()
    assert out["from_version"] == 0
    assert out["to_version"] == runner.code_version()
    assert out["applied"] == [m.id for m in MIGRATIONS]
    assert runner.current_version() == runner.code_version()


def test_migrate_is_idempotent():
    db = _FakeDB()
    runner = _runner(db)
    runner.migrate()
    second = runner.migrate()
    assert second["applied"] == []
    meta = db.collection("er_meta").get("schema")
    assert len(meta["applied"]) == len(MIGRATIONS)  # not duplicated


def test_status_reports_pending_then_up_to_date():
    db = _FakeDB()
    runner = _runner(db)
    before = runner.status()
    assert before["current_version"] == 0
    assert before["up_to_date"] is False
    assert len(before["pending"]) == len(MIGRATIONS)
    runner.migrate()
    after = runner.status()
    assert after["up_to_date"] is True
    assert after["pending"] == []


def test_applies_in_order_and_persists_after_each():
    calls = []
    migs = [
        Migration(2, "second", "", lambda db: calls.append(2)),
        Migration(1, "first", "", lambda db: calls.append(1)),
        Migration(3, "third", "", lambda db: calls.append(3)),
    ]
    db = _FakeDB()
    runner = _runner(db, migrations=migs)
    runner.migrate()
    assert calls == [1, 2, 3]  # sorted by id regardless of registry order
    meta = db.collection("er_meta").get("schema")
    assert [a["id"] for a in meta["applied"]] == [1, 2, 3]


def test_target_limits_applied_migrations():
    migs = [
        Migration(1, "a", "", lambda db: None),
        Migration(2, "b", "", lambda db: None),
        Migration(3, "c", "", lambda db: None),
    ]
    db = _FakeDB()
    runner = _runner(db, migrations=migs)
    out = runner.migrate(target=2)
    assert out["applied"] == [1, 2]
    assert runner.current_version() == 2
    assert [m.id for m in runner.pending()] == [3]


def test_db_newer_than_code_raises():
    migs = [Migration(1, "a", "", lambda db: None)]
    db = _FakeDB()
    # Simulate a DB migrated by newer code.
    db.create_collection("er_meta").insert(
        {"_key": "schema", "version": 5, "applied": []}
    )
    runner = _runner(db, migrations=migs)
    with pytest.raises(SchemaVersionError):
        runner.migrate()


def test_duplicate_ids_rejected():
    migs = [Migration(1, "a", "", lambda db: None), Migration(1, "b", "", lambda db: None)]
    with pytest.raises(ValueError, match="duplicate"):
        MigrationRunner(_FakeDB(), migrations=migs)


def test_resumes_after_partial_failure():
    """A migration that fails leaves earlier ones applied; rerun continues."""
    state = {"fail_second": True}

    def ok(db):
        pass

    def maybe_fail(db):
        if state["fail_second"]:
            raise RuntimeError("boom")

    migs = [
        Migration(1, "a", "", ok),
        Migration(2, "b", "", maybe_fail),
        Migration(3, "c", "", ok),
    ]
    db = _FakeDB()
    runner = _runner(db, migrations=migs)
    with pytest.raises(RuntimeError):
        runner.migrate()
    assert runner.current_version() == 1  # only #1 committed

    state["fail_second"] = False
    out = runner.migrate()
    assert out["applied"] == [2, 3]
    assert runner.current_version() == 3


def test_audit_history_index_migration_is_applied_and_idempotent():
    """Migration 6 must create the audit-history index exactly once.

    Without it, CurationService.history() is a full collection scan plus an
    in-memory sort against an append-only log that only grows.
    """
    db = _FakeDB()
    runner = _runner(db)
    runner.migrate()
    runner.migrate()  # re-running must not duplicate the index

    audit = db.collection("er_audit_log")
    history_indexes = [
        idx for idx in audit.indexes_created
        if idx["fields"] == ["collection", "entity_key", "ts"]
    ]
    assert len(history_indexes) == 1
    assert history_indexes[0]["name"] == "idx_audit_history"
