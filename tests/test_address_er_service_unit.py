from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest

from entity_resolution.services.address_er_service import AddressERService


class _FakeAQL:
    def __init__(self, results: List[Dict[str, Any]]):
        self.results = results
        self.calls = []

    def execute(self, query, bind_vars=None, **kwargs):
        self.calls.append({"query": str(query), "bind_vars": dict(bind_vars or {}), "kwargs": dict(kwargs)})
        return list(self.results)


class _FakeEdgeCollection:
    def __init__(self, fail_on_insert: bool = False):
        self.inserted: List[Dict[str, Any]] = []
        self.truncated = False
        self.fail_on_insert = fail_on_insert

    def truncate(self):
        self.truncated = True

    def insert_many(self, docs):
        if self.fail_on_insert:
            raise RuntimeError("insert failed")
        self.inserted.extend(list(docs))


class _FakeDB:
    def __init__(self):
        self._collections: Dict[str, Any] = {}
        self._views: Dict[str, Any] = {}
        self._analyzers: List[Dict[str, Any]] = []
        self.created_analyzers: List[str] = []
        self.deleted_views: List[str] = []
        self.created_views: List[str] = []
        self.aql = _FakeAQL([])

    def has_collection(self, name: str) -> bool:
        return name in self._collections

    def create_collection(self, name: str, edge: bool = False):
        self._collections[name] = _FakeEdgeCollection()
        return self._collections[name]

    def collection(self, name: str):
        return self._collections[name]

    def analyzers(self):
        return list(self._analyzers)

    def create_analyzer(self, name: str, analyzer_type: str, properties=None, **kwargs):
        self.created_analyzers.append(name)
        self._analyzers.append({"name": name})

    def views(self):
        return [{"name": n} for n in self._views.keys()]

    def delete_view(self, name: str):
        self.deleted_views.append(name)
        self._views.pop(name, None)

    def create_arangosearch_view(self, name: str, properties=None, **kwargs):
        self.created_views.append(name)
        self._views[name] = {"name": name, "properties": properties}

    def properties(self):
        return {"name": "entity_resolution_test"}


def test_setup_analyzers_creates_missing_and_skips_existing() -> None:
    db = _FakeDB()
    db._analyzers = [{"name": "text_normalizer"}]  # one exists
    svc = AddressERService(db=db, collection="addresses", edge_collection="address_sameAs")
    created = svc._setup_analyzers()
    assert "address_normalizer" in created
    assert "text_normalizer" not in created


def test_resolve_analyzer_name_prefers_db_prefixed() -> None:
    db = _FakeDB()
    db._analyzers = [{"name": "entity_resolution_test::address_normalizer"}]
    svc = AddressERService(db=db)
    assert svc._resolve_analyzer_name("address_normalizer") == "entity_resolution_test::address_normalizer"


def test_setup_search_view_drops_existing_and_creates_new() -> None:
    db = _FakeDB()
    db._views = {"addresses_search": {"name": "addresses_search"}}
    svc = AddressERService(db=db, collection="addresses", search_view_name="addresses_search")
    view = svc._setup_search_view()
    assert view == "addresses_search"
    assert "addresses_search" in db.deleted_views
    assert "addresses_search" in db.created_views


def test_find_duplicate_addresses_returns_blocks_and_total_addresses() -> None:
    db = _FakeDB()
    db.aql = _FakeAQL(
        [
            {"block_key": "k1", "addresses": ["addresses/1", "addresses/2"], "size": 2},
            {"block_key": "k2", "addresses": ["addresses/3", "addresses/4", "addresses/5"], "size": 3},
        ]
    )
    svc = AddressERService(db=db, collection="addresses")
    blocks, total = svc._find_duplicate_addresses(max_block_size=10)
    assert set(blocks.keys()) == {"k1", "k2"}
    assert total == 5
    assert db.aql.calls[0]["bind_vars"]["max_block_size"] == 10


def test_create_edges_creates_collection_if_missing_and_batches_inserts() -> None:
    db = _FakeDB()
    svc = AddressERService(db=db, collection="addresses", edge_collection="address_sameAs", config={"edge_batch_size": 2})
    blocks = {"k1": ["a/1", "a/2", "a/3"]}  # 3 nodes -> 3 edges
    created = svc._create_edges(blocks)
    assert created == 3
    assert db.has_collection("address_sameAs")
    edge = db.collection("address_sameAs")
    assert len(edge.inserted) == 3


def test_create_edges_truncates_existing_collection() -> None:
    db = _FakeDB()
    db._collections["address_sameAs"] = _FakeEdgeCollection()
    svc = AddressERService(db=db, collection="addresses", edge_collection="address_sameAs", config={"edge_batch_size": 100})
    created = svc._create_edges({"k1": ["a/1", "a/2"]})
    assert created == 1
    assert db.collection("address_sameAs").truncated is True


def test_create_edges_continues_on_insert_errors() -> None:
    db = _FakeDB()
    db._collections["address_sameAs"] = _FakeEdgeCollection(fail_on_insert=True)
    svc = AddressERService(db=db, collection="addresses", edge_collection="address_sameAs", config={"edge_batch_size": 2})
    # This will hit insert_many and raise; function should continue and return 0 (nothing inserted)
    created = svc._create_edges({"k1": ["a/1", "a/2", "a/3"]})
    assert created == 0


def test_run_uses_csv_or_api_edge_loading_and_optional_clustering(monkeypatch) -> None:
    db = _FakeDB()
    svc = AddressERService(db=db, collection="addresses", config={"edge_loading_method": "csv"})

    monkeypatch.setattr(svc, "_find_duplicate_addresses", lambda max_block_size: ({"k": ["a/1", "a/2"]}, 2))
    monkeypatch.setattr(svc, "_create_edges_via_csv", lambda blocks, csv_path=None: 123)
    monkeypatch.setattr(svc, "_create_edges", lambda blocks: 999)
    monkeypatch.setattr(svc, "_cluster_addresses", lambda min_cluster_size: [["a/1", "a/2"]])

    out = svc.run(create_edges=True, cluster=True, min_cluster_size=2)
    assert out["blocks_found"] == 1
    assert out["addresses_matched"] == 2
    assert out["edges_created"] == 123
    assert out["clusters_found"] == 1

    # Switch to API method
    svc2 = AddressERService(db=db, collection="addresses", config={"edge_loading_method": "api"})
    monkeypatch.setattr(svc2, "_find_duplicate_addresses", lambda max_block_size: ({"k": ["a/1", "a/2"]}, 2))
    monkeypatch.setattr(svc2, "_create_edges", lambda blocks: 7)
    out2 = svc2.run(create_edges=True, cluster=False)
    assert out2["edges_created"] == 7
    assert out2["clusters_found"] is None

