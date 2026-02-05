"""
Unit tests for pipeline_utils.

These tests are DB-free and validate control flow, query construction, and
aggregation logic using lightweight fakes for db/collection/aql.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pytest

from entity_resolution.utils import pipeline_utils


class FakeCursor(list):
    """AQL execute() returns an iterable; list is enough for our usage."""


@dataclass
class AqlCall:
    query: str
    bind_vars: Optional[Dict[str, Any]]


@dataclass
class FakeAQL:
    """
    Fake AQL executor that routes results based on query content.

    Provide a dispatcher callable that returns an iterable result for each call.
    """

    dispatch: Callable[[str, Optional[Dict[str, Any]]], Iterable[Any]]
    calls: List[AqlCall] = field(default_factory=list)

    def execute(self, query: str, bind_vars: Optional[Dict[str, Any]] = None, **kwargs: Any) -> FakeCursor:
        self.calls.append(AqlCall(query=query, bind_vars=bind_vars))
        return FakeCursor(self.dispatch(query, bind_vars))


@dataclass
class FakeCollection:
    count_value: int = 0
    truncated: bool = False
    truncate_raises: Optional[Exception] = None

    def count(self) -> int:
        return self.count_value

    def truncate(self) -> None:
        if self.truncate_raises:
            raise self.truncate_raises
        self.truncated = True
        self.count_value = 0


@dataclass
class FakeDB:
    collections: Dict[str, FakeCollection]
    aql: FakeAQL

    def has_collection(self, name: str) -> bool:
        return name in self.collections

    def collection(self, name: str) -> FakeCollection:
        return self.collections[name]


def test_clean_er_results_truncate_default_behavior() -> None:
    db = FakeDB(
        collections={
            "similarTo": FakeCollection(count_value=10),
            "entity_clusters": FakeCollection(count_value=3),
            "golden_records": FakeCollection(count_value=2),
        },
        aql=FakeAQL(dispatch=lambda q, b: []),
    )

    result = pipeline_utils.clean_er_results(db)
    assert result["errors"] == []
    assert result["removed_counts"] == {"similarTo": 10, "entity_clusters": 3, "golden_records": 2}
    assert result["kept_counts"] == {"similarTo": 0, "entity_clusters": 0, "golden_records": 0}
    assert db.collection("similarTo").truncated is True


def test_clean_er_results_older_than_uses_bind_vars_and_counts_removed() -> None:
    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        if "FILTER doc.timestamp < @older_than" in query:
            assert bind_vars == {"older_than": "2026-01-01T00:00:00"}
            return [{"_key": "a"}, {"_key": "b"}]
        return []

    coll = FakeCollection(count_value=5)
    db = FakeDB(collections={"similarTo": coll}, aql=FakeAQL(dispatch=dispatch))

    result = pipeline_utils.clean_er_results(db, collections=["similarTo"], older_than="2026-01-01T00:00:00")
    assert result["removed_counts"]["similarTo"] == 2
    # kept_counts uses coll.count() after removal query; our fake does not mutate counts here
    assert result["kept_counts"]["similarTo"] == 5
    assert result["errors"] == []


def test_clean_er_results_keep_last_n_removes_older_than_cutoff() -> None:
    calls: List[Tuple[str, Optional[Dict[str, Any]]]] = []

    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        calls.append((query, bind_vars))
        if "SORT doc.timestamp DESC" in query and "LIMIT @n, 1" in query:
            assert bind_vars == {"n": 5}
            return ["2026-02-01T00:00:00"]
        if "FILTER doc.timestamp < @cutoff" in query:
            assert bind_vars == {"cutoff": "2026-02-01T00:00:00"}
            return [{"_key": "x"}]
        return []

    coll = FakeCollection(count_value=7)
    db = FakeDB(collections={"similarTo": coll}, aql=FakeAQL(dispatch=dispatch))

    result = pipeline_utils.clean_er_results(db, collections=["similarTo"], keep_last_n=5)
    assert result["removed_counts"]["similarTo"] == 1
    assert result["kept_counts"]["similarTo"] == 7
    assert len(calls) == 2


def test_clean_er_results_keep_last_n_fewer_than_n_keeps_all() -> None:
    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        if "SORT doc.timestamp DESC" in query and "LIMIT @n, 1" in query:
            return []  # fewer than N
        pytest.fail("Should not execute removal query when fewer than N docs exist")

    coll = FakeCollection(count_value=3)
    db = FakeDB(collections={"similarTo": coll}, aql=FakeAQL(dispatch=dispatch))

    result = pipeline_utils.clean_er_results(db, collections=["similarTo"], keep_last_n=10)
    assert result["removed_counts"]["similarTo"] == 0
    assert result["kept_counts"]["similarTo"] == 3
    assert result["errors"] == []


def test_clean_er_results_truncate_error_is_recorded() -> None:
    coll = FakeCollection(count_value=10, truncate_raises=RuntimeError("boom"))
    db = FakeDB(collections={"similarTo": coll}, aql=FakeAQL(dispatch=lambda q, b: []))

    result = pipeline_utils.clean_er_results(db, collections=["similarTo"])
    assert result["removed_counts"] == {}
    assert result["kept_counts"] == {}
    assert len(result["errors"]) == 1
    assert result["errors"][0]["collection"] == "similarTo"
    assert "boom" in result["errors"][0]["error"]


def test_count_inferred_edges_missing_collection_raises() -> None:
    db = FakeDB(collections={}, aql=FakeAQL(dispatch=lambda q, b: []))
    with pytest.raises(ValueError, match="does not exist"):
        pipeline_utils.count_inferred_edges(db, edge_collection="similarTo")


def test_count_inferred_edges_basic_counts_avg_and_distribution() -> None:
    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        if "COLLECT WITH COUNT INTO cnt RETURN cnt" in query and "FILTER e.inferred == true" in query:
            return [3]
        if "AGGREGATE avg_conf = AVG" in query:
            return [0.91234]
        if "LET range = FLOOR" in query:
            return [{"bucket": 0.9, "count": 2}, {"bucket": 0.95, "count": 1}]
        return []

    edge_coll = FakeCollection(count_value=10)
    db = FakeDB(collections={"similarTo": edge_coll}, aql=FakeAQL(dispatch=dispatch))

    stats = pipeline_utils.count_inferred_edges(db, edge_collection="similarTo")
    assert stats["total_edges"] == 10
    assert stats["inferred_edges"] == 3
    assert stats["direct_edges"] == 7
    assert stats["avg_confidence"] == 0.9123
    assert stats["confidence_distribution"] == {"0.90-0.95": 2, "0.95-1.00": 1}


def test_count_inferred_edges_with_threshold_filters_queries() -> None:
    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        # All three queries should include the threshold filter
        assert "FILTER e.confidence >= 0.85" in query
        if "COLLECT WITH COUNT INTO cnt RETURN cnt" in query:
            return [1]
        if "AGGREGATE avg_conf = AVG" in query:
            return [0.9]
        if "LET range = FLOOR" in query:
            return []
        return []

    edge_coll = FakeCollection(count_value=5)
    db = FakeDB(collections={"similarTo": edge_coll}, aql=FakeAQL(dispatch=dispatch))

    stats = pipeline_utils.count_inferred_edges(db, edge_collection="similarTo", confidence_threshold=0.85)
    assert stats["inferred_edges"] == 1
    assert stats["direct_edges"] == 4


def test_validate_edge_quality_aggregates_issues_and_limits_sample_details() -> None:
    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        if "FILTER e.confidence == null" in query:
            return [1]
        if "FILTER e.confidence < 0.75" in query:
            return [2]
        if "FILTER e._from == e._to" in query:
            return [1]
        if "LIMIT 100" in query and "has_match_details" in query:
            # Return 12, but API should only return first 10
            return [{"_from": "a", "_to": "b", "confidence": 0.9, "method": "x", "has_match_details": False}] * 12
        return []

    edge_coll = FakeCollection(count_value=10)
    db = FakeDB(collections={"similarTo": edge_coll}, aql=FakeAQL(dispatch=dispatch))

    result = pipeline_utils.validate_edge_quality(db, edge_collection="similarTo", min_confidence=0.75, sample_size=100)
    assert result["total_edges"] == 10
    assert result["invalid_edges"] == 4
    assert result["valid_edges"] == 6
    assert result["valid"] is False
    assert {i["type"] for i in result["issues"]} == {"missing_confidence", "below_threshold", "self_loop"}
    assert len(result["sample_details"]) == 10


def test_validate_edge_quality_missing_collection_raises() -> None:
    db = FakeDB(collections={}, aql=FakeAQL(dispatch=lambda q, b: []))
    with pytest.raises(ValueError, match="does not exist"):
        pipeline_utils.validate_edge_quality(db, edge_collection="similarTo")


def test_get_pipeline_statistics_missing_collections_is_graceful() -> None:
    db = FakeDB(collections={}, aql=FakeAQL(dispatch=lambda q, b: []))
    stats = pipeline_utils.get_pipeline_statistics(db, vertex_collection="v")
    assert "timestamp" in stats
    assert "entities" not in stats
    assert "edges" not in stats
    assert "clusters" not in stats


def test_get_pipeline_statistics_complete_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch count_inferred_edges so this test focuses on aggregation/formatting logic.
    monkeypatch.setattr(
        pipeline_utils,
        "count_inferred_edges",
        lambda db, edge_collection="similarTo", confidence_threshold=None: {
            "total_edges": 10,
            "inferred_edges": 2,
            "direct_edges": 8,
            "avg_confidence": 0.9,
            "confidence_distribution": {},
            "timestamp": "t",
        },
    )

    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        if "RETURN SUM(cluster.size)" in query:
            return [30]
        if "avg_size = AVG" in query and "max_size = MAX" in query:
            return [{"avg_size": 3.2, "max_size": 10}]
        if "LET size_bucket" in query:
            return [{"bucket": "2", "count": 2}, {"bucket": "4-10", "count": 3}]
        return []

    db = FakeDB(
        collections={
            "v": FakeCollection(count_value=100),
            "entity_clusters": FakeCollection(count_value=5),
            "similarTo": FakeCollection(count_value=10),
        },
        aql=FakeAQL(dispatch=dispatch),
    )

    stats = pipeline_utils.get_pipeline_statistics(db, vertex_collection="v")
    assert stats["entities"]["total"] == 100
    assert stats["entities"]["clustered"] == 30
    assert stats["entities"]["unclustered"] == 70
    assert stats["edges"]["total"] == 10
    assert stats["clusters"]["total"] == 5
    assert stats["clusters"]["max_size"] == 10
    assert stats["clusters"]["size_distribution"] == {"2": 2, "4-10": 3}
    assert stats["performance"]["actual_edges"] == 10
    assert stats["performance"]["total_possible_pairs"] == 4950


def test_get_pipeline_statistics_empty_clusters_sets_zero_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline_utils,
        "count_inferred_edges",
        lambda db, edge_collection="similarTo", confidence_threshold=None: {
            "total_edges": 0,
            "inferred_edges": 0,
            "direct_edges": 0,
            "avg_confidence": None,
            "confidence_distribution": {},
            "timestamp": "t",
        },
    )

    db = FakeDB(
        collections={
            "v": FakeCollection(count_value=0),
            "entity_clusters": FakeCollection(count_value=0),
            "similarTo": FakeCollection(count_value=0),
        },
        aql=FakeAQL(dispatch=lambda q, b: []),
    )

    stats = pipeline_utils.get_pipeline_statistics(db, vertex_collection="v")
    assert stats["clusters"]["total"] == 0
    assert stats["clusters"]["avg_size"] == 0
    assert stats["clusters"]["size_distribution"] == {}
    assert stats["entities"]["clustering_rate"] == 0

