from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from entity_resolution.services.blocking_service import BlockingService


class _FakeAQL:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self._results_by_key: Dict[str, List[str]] = {}

    def when_query_contains(self, needle: str, results: List[str]) -> None:
        self._results_by_key[needle] = results

    def execute(self, query, bind_vars=None):
        q = str(query)
        self.calls.append({"query": q, "bind_vars": dict(bind_vars or {})})
        for needle, results in self._results_by_key.items():
            if needle in q:
                return list(results)
        return []


class _FakeCollection:
    def __init__(self, docs: Dict[str, Dict[str, Any]]):
        self.docs = docs

    def get(self, key: str):
        return self.docs.get(key)


class _FakeDB:
    def __init__(self, docs: Dict[str, Dict[str, Any]]):
        self.aql = _FakeAQL()
        self._collections = {"customers": _FakeCollection(docs)}

    def collection(self, name: str):
        return self._collections[name]

    def analyzers(self):
        return []

    def has_view(self, _name: str) -> bool:
        return False

    def create_analyzer(self, **kwargs):
        return None

    def create_arangosearch_view(self, *_args, **_kwargs):
        return None


def test_blocking_service_emits_deprecation_warning_on_init() -> None:
    with pytest.warns(DeprecationWarning):
        BlockingService()


def test_get_blocking_analyzers_and_view_config_shapes() -> None:
    with pytest.warns(DeprecationWarning):
        svc = BlockingService()
    analyzers = svc._get_blocking_analyzers()
    assert "blocking_ngram" in analyzers
    view = svc._get_blocking_view_config("customers")
    assert "links" in view and "customers" in view["links"]
    assert view["links"]["customers"]["includeAllFields"] is False


def test_apply_blocking_strategy_dispatch_and_unknown() -> None:
    with pytest.warns(DeprecationWarning):
        svc = BlockingService()
    db = _FakeDB({"customers/1": {"_id": "customers/1"}})
    target = {"_id": "customers/1", "first_name": "Jane", "last_name": "Doe", "email": "x@example.com", "phone": "555"}

    # Patch concrete methods to prove dispatch
    svc._exact_blocking = lambda *_a, **_k: ["customers/2"]  # type: ignore[assignment]
    svc._ngram_blocking = lambda *_a, **_k: ["customers/3"]  # type: ignore[assignment]
    svc._phonetic_blocking = lambda *_a, **_k: ["customers/4"]  # type: ignore[assignment]
    svc._sorted_neighborhood_blocking = lambda *_a, **_k: ["customers/5"]  # type: ignore[assignment]

    assert svc._apply_blocking_strategy(db, "customers", target, "exact", 10) == ["customers/2"]
    assert svc._apply_blocking_strategy(db, "customers", target, "ngram", 10) == ["customers/3"]
    assert svc._apply_blocking_strategy(db, "customers", target, "phonetic", 10) == ["customers/4"]
    assert svc._apply_blocking_strategy(db, "customers", target, "sorted_neighborhood", 10) == ["customers/5"]
    assert svc._apply_blocking_strategy(db, "customers", target, "unknown", 10) == []


def test_exact_ngram_phonetic_and_sorted_neighborhood_build_queries() -> None:
    with pytest.warns(DeprecationWarning):
        svc = BlockingService()
    db = _FakeDB({})
    db.aql.when_query_contains("FILTER doc.email", ["customers/2"])
    db.aql.when_query_contains("FILTER doc.phone", ["customers/3"])
    db.aql.when_query_contains("FILTER doc.last_name", ["customers/4"])
    db.aql.when_query_contains("LEFT(doc.last_name, 3)", ["customers/5"])
    db.aql.when_query_contains("LEFT(doc.first_name, 3)", ["customers/6"])
    db.aql.when_query_contains("SOUNDEX(doc.first_name)", ["customers/7"])
    db.aql.when_query_contains("SOUNDEX(doc.last_name)", ["customers/8"])
    db.aql.when_query_contains("LET doc_key", [{"_id": "customers/9", "sort_key": "DOEJANE", "distance": 1}])

    target = {"_id": "customers/1", "first_name": "Jane", "last_name": "Doe", "email": "x@example.com", "phone": "555"}

    exact = svc._exact_blocking(db, "customers", target, limit=10)
    assert set(exact) >= {"customers/2", "customers/3", "customers/4"}

    ngram = svc._ngram_blocking(db, "customers", target, limit=10)
    assert set(ngram) >= {"customers/5", "customers/6"}

    phon = svc._phonetic_blocking(db, "customers", target, limit=10)
    assert set(phon) >= {"customers/7", "customers/8"}

    sorted_nb = svc._sorted_neighborhood_blocking(db, "customers", target, limit=10)
    assert "customers/9" in sorted_nb


def test_generate_candidates_via_python_uses_strategies_and_fetches_docs(monkeypatch) -> None:
    # Build fake arango module for the internal import: `from arango import ArangoClient`
    docs = {
        "customers/1": {"_id": "customers/1", "_key": "1"},
        "customers/2": {"_id": "customers/2", "_key": "2"},
        "customers/3": {"_id": "customers/3", "_key": "3"},
    }

    fake_db = _FakeDB(docs)

    class _FakeArangoClient:
        def __init__(self, hosts: str):
            self.hosts = hosts

        def db(self, *_args, **_kwargs):
            return fake_db

    monkeypatch.setitem(sys.modules, "arango", SimpleNamespace(ArangoClient=_FakeArangoClient))

    with pytest.warns(DeprecationWarning):
        svc = BlockingService()

    # Avoid exercising blocking strategy internals here; focus on orchestration.
    svc._apply_blocking_strategy = lambda *_a, **_k: ["customers/2", "customers/3"]  # type: ignore[assignment]

    out = svc._generate_candidates_via_python("customers", "customers/1", ["exact", "ngram"], limit=10)
    assert out["success"] is True
    assert out["statistics"]["unique_candidates"] == 2
    assert len(out["candidates"]) == 2

