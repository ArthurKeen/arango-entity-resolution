from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from entity_resolution.similarity.ann_adapter import ANNAdapter


class _FakeCollection:
    def __init__(self, docs: Dict[str, Dict[str, Any]]):
        self._docs = docs

    def get(self, key: str):
        return self._docs.get(key)

    def count(self) -> int:
        return len(self._docs)


class _FakeAQL:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self.raise_on_contains: Optional[str] = None
        self._return_rows: List[List[Dict[str, Any]]] = []

    def queue(self, rows: List[Dict[str, Any]]) -> None:
        self._return_rows.append(rows)

    def execute(self, query, bind_vars=None, **kwargs):
        q = str(query)
        self.calls.append({"query": q, "bind_vars": dict(bind_vars or {}), "kwargs": dict(kwargs)})
        if self.raise_on_contains and self.raise_on_contains in q:
            raise RuntimeError("query failed")
        return list(self._return_rows.pop(0) if self._return_rows else [])


class _FakeDB:
    def __init__(self, version: str = "3.12.0", docs: Optional[Dict[str, Dict[str, Any]]] = None):
        self._version = version
        self._docs = docs or {}
        self.aql = _FakeAQL()

    def properties(self):
        return {"version": self._version}

    def collection(self, name: str):
        assert name == "customers"
        return _FakeCollection(self._docs)


def test_init_force_brute_force_sets_method() -> None:
    db = _FakeDB()
    adapter = ANNAdapter(db=db, collection="customers", force_brute_force=True)
    assert adapter.method == "brute_force"


def test_detect_capabilities_parses_version_and_sets_method() -> None:
    db = _FakeDB(version="3.12.1")
    adapter = ANNAdapter(db=db, collection="customers", force_brute_force=False)
    assert adapter.method in ("arango_vector_search", "brute_force")
    assert adapter.arango_version == (3, 12, 1)


def test_find_similar_vectors_requires_vector_or_doc_key() -> None:
    db = _FakeDB()
    adapter = ANNAdapter(db=db, collection="customers", force_brute_force=True)
    with pytest.raises(ValueError):
        adapter.find_similar_vectors(query_vector=None, query_doc_key=None)


def test_find_similar_vectors_fetches_query_vector_from_doc_key_and_excludes_self() -> None:
    db = _FakeDB(docs={"a": {"_key": "a", "embedding_vector": [1.0, 0.0]}})
    db.aql.queue([{"doc_key": "b", "similarity": 0.9, "method": "brute_force"}])

    adapter = ANNAdapter(db=db, collection="customers", force_brute_force=True)
    res = adapter.find_similar_vectors(query_vector=None, query_doc_key="a", limit=5, exclude_self=True)
    assert res and res[0]["doc_key"] == "b"
    call = db.aql.calls[-1]
    assert "FILTER doc._key != @exclude_key" in call["query"]
    assert call["bind_vars"]["exclude_key"] == "a"


def test_find_with_arango_vector_search_falls_back_to_brute_force_on_query_failure() -> None:
    # vector search query will raise, brute force will return
    db = _FakeDB(docs={"a": {"_key": "a", "embedding_vector": [1.0, 0.0]}})
    db.aql.raise_on_contains = "COSINE_SIMILARITY"
    db.aql.queue([{"doc_key": "x", "similarity": 0.8, "method": "brute_force"}])

    adapter = ANNAdapter(db=db, collection="customers", force_brute_force=False)
    # Force method to attempt vector search path
    adapter._method = "arango_vector_search"

    res = adapter.find_similar_vectors(
        query_vector=None,
        query_doc_key="a",
        similarity_threshold=0.7,
        limit=10,
        blocking_field="state",
        blocking_value="CA",
        filters={"city": {"equals": "SF"}},
    )
    assert res and res[0]["method"] == "brute_force"
    # brute-force bind vars include filters
    last = db.aql.calls[-1]["bind_vars"]
    assert last["blocking_value"] == "CA"
    assert last["filter_city"] == "SF"


def test_find_all_pairs_builds_query_and_binds_method_and_filters() -> None:
    db = _FakeDB()
    db.aql.queue([{"doc1_key": "1", "doc2_key": "2", "similarity": 0.9, "method": "brute_force"}])
    adapter = ANNAdapter(db=db, collection="customers", force_brute_force=True)
    pairs = adapter.find_all_pairs(similarity_threshold=0.8, limit_per_entity=3, blocking_field="state", filters={"state": {"equals": "CA"}})
    assert pairs and pairs[0]["doc1_key"] == "1"
    call = db.aql.calls[-1]
    assert call["bind_vars"]["method"] == "brute_force"
    assert call["bind_vars"]["filter_state"] == "CA"

