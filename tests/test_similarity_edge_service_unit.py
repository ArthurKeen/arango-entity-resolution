"""
Unit tests for SimilarityEdgeService.

These tests are intentionally DB-free (no Docker/Arango required). We use
lightweight fakes to validate edge shaping, deterministic key behavior,
batch insertion behavior, and AQL query construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pytest

from entity_resolution.services.similarity_edge_service import SimilarityEdgeService


class FakeCursor(list):
    """Simple iterable cursor returned from FakeAQL.execute()."""


@dataclass
class FakeAQL:
    last_query: Optional[str] = None
    next_result: Iterable[Dict[str, Any]] = field(default_factory=list)

    def execute(self, query: str, *args: Any, **kwargs: Any) -> FakeCursor:
        self.last_query = query
        return FakeCursor(self.next_result)


@dataclass
class InsertCall:
    docs: List[Dict[str, Any]]
    overwrite_mode: Optional[str]


@dataclass
class FakeEdgeCollection:
    insert_calls: List[InsertCall] = field(default_factory=list)
    raise_on_call_indexes: set[int] = field(default_factory=set)
    insert_attempts: int = 0

    def insert_many(self, docs: List[Dict[str, Any]], overwrite_mode: Optional[str] = None) -> None:
        call_index = self.insert_attempts
        self.insert_attempts += 1
        if call_index in self.raise_on_call_indexes:
            raise RuntimeError("insert_many failure (simulated)")
        self.insert_calls.append(InsertCall(docs=list(docs), overwrite_mode=overwrite_mode))


@dataclass
class FakeDB:
    """Minimal DB facade used by SimilarityEdgeService."""

    has_collection_value: bool = True
    created_collections: List[Tuple[str, bool]] = field(default_factory=list)
    edge_collection: FakeEdgeCollection = field(default_factory=FakeEdgeCollection)
    aql: FakeAQL = field(default_factory=FakeAQL)

    def has_collection(self, name: str) -> bool:
        return self.has_collection_value

    def create_collection(self, name: str, edge: bool = False) -> FakeEdgeCollection:
        self.created_collections.append((name, edge))
        return self.edge_collection

    def collection(self, name: str) -> FakeEdgeCollection:
        return self.edge_collection


@pytest.fixture
def fake_db() -> FakeDB:
    return FakeDB(has_collection_value=True)


def _flatten_inserted_docs(edge_collection: FakeEdgeCollection) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for call in edge_collection.insert_calls:
        docs.extend(call.docs)
    return docs


def test_generate_deterministic_key_order_independent(fake_db: FakeDB) -> None:
    svc = SimilarityEdgeService(db=fake_db, edge_collection="similarTo", vertex_collection="v", use_deterministic_keys=True)

    a = "v/1"
    b = "v/2"
    assert svc._generate_deterministic_key(a, b) == svc._generate_deterministic_key(b, a)


def test_create_edges_deterministic_keys_sets_key_and_overwrite_ignore(fake_db: FakeDB) -> None:
    svc = SimilarityEdgeService(db=fake_db, edge_collection="similarTo", vertex_collection="v", use_deterministic_keys=True)

    matches = [("1", "2", 0.98765)]
    created = svc.create_edges(matches, metadata={"method": "unit_test"})

    assert created == 1
    assert len(fake_db.edge_collection.insert_calls) == 1
    call = fake_db.edge_collection.insert_calls[0]
    assert call.overwrite_mode == "ignore"

    docs = call.docs
    assert len(docs) == 1
    edge = docs[0]
    assert edge["_from"] == "v/1"
    assert edge["_to"] == "v/2"
    assert edge["similarity"] == 0.9877  # rounded to 4 decimals
    assert edge["method"] == "unit_test"
    assert "timestamp" in edge
    assert "_key" in edge


def test_create_edges_without_deterministic_keys_uses_no_overwrite_and_no_key() -> None:
    db = FakeDB(has_collection_value=True)
    svc = SimilarityEdgeService(db=db, edge_collection="similarTo", vertex_collection="v", use_deterministic_keys=False)

    created = svc.create_edges([("1", "2", 0.5)])

    assert created == 1
    call = db.edge_collection.insert_calls[0]
    assert call.overwrite_mode is None
    edge = call.docs[0]
    assert "_key" not in edge


def test_create_edges_bidirectional_creates_reverse_edges_with_same_key(fake_db: FakeDB) -> None:
    svc = SimilarityEdgeService(db=fake_db, edge_collection="similarTo", vertex_collection="v", use_deterministic_keys=True)

    created = svc.create_edges([("1", "2", 0.9)], bidirectional=True)
    assert created == 2

    docs = _flatten_inserted_docs(fake_db.edge_collection)
    assert len(docs) == 2
    forward = next(d for d in docs if d["_from"] == "v/1" and d["_to"] == "v/2")
    reverse = next(d for d in docs if d["_from"] == "v/2" and d["_to"] == "v/1")
    assert forward["_key"] == reverse["_key"]


def test_create_edges_handles_batch_insert_exception_and_continues() -> None:
    db = FakeDB(has_collection_value=True)
    db.edge_collection.raise_on_call_indexes = {0}  # fail first batch insert

    svc = SimilarityEdgeService(
        db=db,
        edge_collection="similarTo",
        vertex_collection="v",
        batch_size=1,  # force one match per batch
        use_deterministic_keys=True,
    )

    created = svc.create_edges([("1", "2", 0.8), ("3", "4", 0.7)])

    # First batch fails, second batch succeeds (1 edge)
    assert created == 1
    assert len(db.edge_collection.insert_calls) == 1  # only successful call recorded

    stats = svc.get_statistics()
    assert stats["edges_created"] == 1
    assert stats["batches_processed"] == 1


def test_create_edges_detailed_skips_missing_keys(fake_db: FakeDB) -> None:
    svc = SimilarityEdgeService(db=fake_db, edge_collection="similarTo", vertex_collection="v", use_deterministic_keys=True)

    matches = [
        {"doc1_key": "1", "doc2_key": "2", "similarity": 0.9, "blocking_method": "x"},
        {"doc1_key": "3", "similarity": 0.5},  # missing doc2_key -> skipped
        {"doc2_key": "4", "similarity": 0.5},  # missing doc1_key -> skipped
    ]
    created = svc.create_edges_detailed(matches)

    assert created == 1
    docs = _flatten_inserted_docs(fake_db.edge_collection)
    assert len(docs) == 1
    edge = docs[0]
    assert edge["_from"] == "v/1"
    assert edge["_to"] == "v/2"
    assert edge["similarity"] == 0.9
    assert edge["blocking_method"] == "x"
    assert "_key" in edge


def test_clear_edges_builds_query_with_method_filter_and_returns_removed_count() -> None:
    db = FakeDB(has_collection_value=True)
    db.aql.next_result = [{"_key": "1"}, {"_key": "2"}]

    svc = SimilarityEdgeService(db=db, edge_collection="similarTo", vertex_collection="v")
    removed = svc.clear_edges(method="phone_blocking")

    assert removed == 2
    assert db.aql.last_query is not None
    assert 'FOR e IN similarTo' in db.aql.last_query
    assert 'FILTER e.method == "phone_blocking"' in db.aql.last_query
    assert "REMOVE e IN similarTo" in db.aql.last_query


def test_clear_edges_builds_query_with_older_than_filter() -> None:
    db = FakeDB(has_collection_value=True)
    db.aql.next_result = []

    svc = SimilarityEdgeService(db=db, edge_collection="similarTo", vertex_collection="v")
    removed = svc.clear_edges(older_than="2026-01-01T00:00:00")

    assert removed == 0
    assert db.aql.last_query is not None
    assert 'FILTER e.timestamp < "2026-01-01T00:00:00"' in db.aql.last_query


def test_init_auto_create_collection_false_does_not_create_collection() -> None:
    db = FakeDB(has_collection_value=False)

    _ = SimilarityEdgeService(db=db, edge_collection="similarTo", auto_create_collection=False)

    assert db.created_collections == []

