from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from entity_resolution.utils import view_utils


class _FakeAQL:
    def __init__(self, should_raise: Optional[Exception] = None):
        self.should_raise = should_raise
        self.calls: List[Dict[str, Any]] = []

    def execute(self, query, bind_vars=None, **kwargs):
        self.calls.append({"query": str(query), "bind_vars": dict(bind_vars or {}), "kwargs": dict(kwargs)})
        if self.should_raise:
            raise self.should_raise
        return [1]


class _FakeDB:
    def __init__(
        self,
        analyzers: List[str] | None = None,
        views: List[str] | None = None,
        db_name: str | None = "testdb",
        aql_exc: Optional[Exception] = None,
    ):
        self._analyzers = [{"name": a} for a in (analyzers or [])]
        self._views = [{"name": v} for v in (views or [])]
        self._db_name = db_name
        self.aql = _FakeAQL(should_raise=aql_exc)
        self.deleted_views: List[str] = []
        self.created_views: List[Dict[str, Any]] = []

    def analyzers(self):
        return list(self._analyzers)

    def views(self):
        return list(self._views)

    def properties(self):
        if self._db_name is None:
            raise AttributeError("no props")
        return {"name": self._db_name}

    @property
    def name(self):
        if self._db_name is None:
            raise AttributeError("no name")
        return self._db_name

    def delete_view(self, name: str):
        self.deleted_views.append(name)
        self._views = [v for v in self._views if v["name"] != name]

    def create_arangosearch_view(self, name: str, properties=None, **kwargs):
        self.created_views.append({"name": name, "properties": properties})
        self._views.append({"name": name})


def test_resolve_analyzer_name_returns_unprefixed_if_exists() -> None:
    db = _FakeDB(analyzers=["identity", "text_en"])
    assert view_utils.resolve_analyzer_name(db, "identity") == "identity"


def test_resolve_analyzer_name_returns_db_prefixed_if_exists() -> None:
    db = _FakeDB(analyzers=["testdb::address_normalizer"], db_name="testdb")
    assert view_utils.resolve_analyzer_name(db, "address_normalizer") == "testdb::address_normalizer"


def test_resolve_analyzer_name_falls_back_to_any_prefixed_suffix_match() -> None:
    db = _FakeDB(analyzers=["otherdb::address_normalizer"], db_name="testdb")
    assert view_utils.resolve_analyzer_name(db, "address_normalizer") == "otherdb::address_normalizer"


def test_verify_view_analyzers_returns_false_if_view_missing() -> None:
    db = _FakeDB(views=["some_other_view"])
    ok, err = view_utils.verify_view_analyzers(db, "my_view", "coll")
    assert ok is False
    assert "does not exist" in (err or "")


def test_verify_view_analyzers_uses_default_test_query_and_succeeds() -> None:
    db = _FakeDB(views=["my_view"])
    ok, err = view_utils.verify_view_analyzers(db, "my_view", "coll", test_query=None)
    assert ok is True
    assert err is None
    assert "FOR doc IN my_view LIMIT 1 RETURN 1" in db.aql.calls[0]["query"]


def test_verify_view_analyzers_classifies_analyzer_errors() -> None:
    db = _FakeDB(views=["my_view"], aql_exc=RuntimeError("failed to build scorers: analyzer missing"))
    ok, err = view_utils.verify_view_analyzers(db, "my_view", "coll")
    assert ok is False
    assert err is not None and "Analyzer configuration issue" in err


def test_verify_view_analyzers_classifies_other_errors() -> None:
    db = _FakeDB(views=["my_view"], aql_exc=RuntimeError("some other failure"))
    ok, err = view_utils.verify_view_analyzers(db, "my_view", "coll")
    assert ok is False
    assert err is not None and "View accessibility error" in err


def test_fix_view_analyzer_names_deletes_existing_and_creates_view(monkeypatch) -> None:
    # Prevent real sleep in tests
    monkeypatch.setattr(view_utils.time, "sleep", lambda _s: None)

    db = _FakeDB(analyzers=["testdb::text_en", "identity"], views=["my_view"], db_name="testdb")
    result = view_utils.fix_view_analyzer_names(
        db=db,
        view_name="my_view",
        collection_name="companies",
        field_analyzers={"name": ["text_en", "identity"]},
        view_properties=None,
        wait_seconds=1,
    )
    assert result["view_created"] is True
    assert db.deleted_views == ["my_view"]
    assert db.created_views
    created = db.created_views[0]
    assert created["name"] == "my_view"
    # analyzer resolution should have applied db prefix for text_en
    assert result["analyzers_resolved"]["name"][0].endswith("::text_en")


def test_verify_and_fix_view_analyzers_no_fix_when_auto_fix_false(monkeypatch) -> None:
    db = _FakeDB(views=["my_view"], aql_exc=RuntimeError("failed to build scorers"))
    out = view_utils.verify_and_fix_view_analyzers(
        db=db,
        view_name="my_view",
        collection_name="companies",
        field_analyzers={"name": ["text_en"]},
        auto_fix=False,
    )
    assert out["verified"] is False
    assert out["fixed"] is False
    assert out["fix_result"] is None


def test_verify_and_fix_view_analyzers_attempts_fix_and_reverifies(monkeypatch) -> None:
    # Make verify_view_analyzers fail once then succeed
    calls = {"n": 0}

    def _fake_verify(db, view_name, collection_name, test_query=None):
        calls["n"] += 1
        return (calls["n"] >= 2, None if calls["n"] >= 2 else "Analyzer configuration issue: missing analyzer")

    monkeypatch.setattr(view_utils, "verify_view_analyzers", _fake_verify)
    monkeypatch.setattr(view_utils, "fix_view_analyzer_names", lambda *a, **k: {"view_created": True})

    db = _FakeDB(views=["my_view"])
    out = view_utils.verify_and_fix_view_analyzers(
        db=db,
        view_name="my_view",
        collection_name="companies",
        field_analyzers={"name": ["text_en"]},
        auto_fix=True,
    )
    assert out["fixed"] is True
    assert out["verified"] is True

