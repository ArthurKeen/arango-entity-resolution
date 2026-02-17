from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from entity_resolution.data.data_manager import DataManager


class _FakeCollection:
    def __init__(self):
        self.inserted: List[Dict[str, Any]] = []

    def insert_many(self, batch):
        self.inserted.extend(list(batch))
        # arango driver returns list of meta docs; we only need length
        return [{} for _ in batch]

    def properties(self):
        return {"type": 2, "status": 3}

    def count(self):
        return len(self.inserted)

    def indexes(self):
        return [{"type": "primary"}]


class _FakeAQL:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = rows
        self.calls = []

    def execute(self, query, bind_vars=None, **kwargs):
        self.calls.append({"query": str(query), "bind_vars": dict(bind_vars or {}), "kwargs": dict(kwargs)})
        return list(self.rows)


class _FakeDB:
    def __init__(self):
        self._colls: Dict[str, _FakeCollection] = {}
        self.aql = _FakeAQL([])

    def has_collection(self, name: str) -> bool:
        return name in self._colls

    def create_collection(self, name: str, edge: bool = False):
        self._colls[name] = _FakeCollection()
        return self._colls[name]

    def collection(self, name: str):
        return self._colls[name]


def _make_manager(fake_db: _FakeDB) -> DataManager:
    dm = DataManager()
    # DataManager inconsistently references `self.database` (DatabaseMixin property)
    # and `self.db` (legacy attribute). Provide both.
    dm._database = fake_db  # type: ignore[attr-defined]
    dm.db = fake_db  # type: ignore[attr-defined]
    return dm


def test_create_collection_creates_and_is_idempotent() -> None:
    fake_db = _FakeDB()
    dm = _make_manager(fake_db)
    assert dm.create_collection("customers") is True
    assert dm.create_collection("customers") is True
    assert fake_db.has_collection("customers") is True


def test_load_data_from_file_supports_list_and_dict_wrappers(tmp_path: Path) -> None:
    fake_db = _FakeDB()
    dm = _make_manager(fake_db)

    # list format
    p1 = tmp_path / "data1.json"
    p1.write_text(json.dumps([{"_key": "1"}, {"_key": "2"}]))
    out1 = dm.load_data_from_file(str(p1), "customers", batch_size=1)
    assert out1["success"] is True
    assert out1["total_records"] == 2
    assert out1["inserted_records"] == 2

    # dict with "customers"
    p2 = tmp_path / "data2.json"
    p2.write_text(json.dumps({"customers": [{"_key": "3"}]}))
    out2 = dm.load_data_from_file(str(p2), "customers2", batch_size=100)
    assert out2["success"] is True
    assert out2["total_records"] == 1

    # dict with "data"
    p3 = tmp_path / "data3.json"
    p3.write_text(json.dumps({"data": [{"_key": "4"}, {"_key": "5"}]}))
    out3 = dm.load_data_from_file(str(p3), "customers3", batch_size=100)
    assert out3["success"] is True
    assert out3["total_records"] == 2


def test_get_collection_stats_errors_when_missing() -> None:
    fake_db = _FakeDB()
    dm = _make_manager(fake_db)
    out = dm.get_collection_stats("missing")
    assert out["success"] is False


def test_get_collection_stats_returns_properties_when_present() -> None:
    fake_db = _FakeDB()
    dm = _make_manager(fake_db)
    dm.create_collection("customers")
    out = dm.get_collection_stats("customers")
    assert out["success"] is True
    assert out["count"] == 0
    assert out["indexes"]


def test_sample_records_returns_empty_when_collection_missing() -> None:
    fake_db = _FakeDB()
    dm = _make_manager(fake_db)
    assert dm.sample_records("missing", limit=5) == []


def test_sample_records_executes_aql_when_collection_exists() -> None:
    fake_db = _FakeDB()
    fake_db._colls["customers"] = _FakeCollection()
    fake_db.aql = _FakeAQL([{"_key": "1"}])
    dm = _make_manager(fake_db)
    rows = dm.sample_records("customers", limit=1)
    assert rows == [{"_key": "1"}]
    assert "FOR doc IN customers" in fake_db.aql.calls[0]["query"]
    assert "LIMIT 1" in fake_db.aql.calls[0]["query"]


def test_load_data_from_dataframe_returns_error_when_pandas_unavailable(monkeypatch) -> None:
    from entity_resolution.data import data_manager as dm_mod

    fake_db = _FakeDB()
    dm = _make_manager(fake_db)

    monkeypatch.setattr(dm_mod, "PANDAS_AVAILABLE", False)
    monkeypatch.setattr(dm_mod, "pd", None)
    out = dm.load_data_from_dataframe(df=None, collection_name="customers")  # type: ignore[arg-type]
    assert out["success"] is False
    assert "pandas not available" in out["error"]

