from __future__ import annotations

import pytest

from entity_resolution.core.entity_resolver import EntityResolutionPipeline


class _FakeDataManager:
    def __init__(self, connect_ok: bool = True, records=None):
        self._connect_ok = connect_ok
        self._records = records or []

    def connect(self) -> bool:
        return self._connect_ok

    def load_data_from_file(self, path: str, collection_name: str):
        return {"success": True, "inserted_records": 3}

    def load_data_from_dataframe(self, df, collection_name: str):
        return {"success": True, "inserted_records": 2}

    def validate_data_quality(self, collection_name: str):
        return {"overall_quality_score": 0.9}

    def initialize_test_collections(self):
        return {"success": True}

    def sample_records(self, collection_name: str, limit: int = 10):
        return list(self._records)


class _FakeService:
    def __init__(self, ok: bool = True, setup_ok: bool = True):
        self._ok = ok
        self._setup_ok = setup_ok

    def connect(self) -> bool:
        return self._ok

    def setup_for_collections(self, collections):
        return {"success": self._setup_ok, "analyzers": {"a": 1}, "views": {"v": 1}}


def test_load_data_requires_connection() -> None:
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.connected = False
    out = p.load_data(source="file.json", collection_name="c")
    assert out["success"] is False
    assert "not connected" in out["error"].lower()


def test_connect_fails_if_data_manager_fails() -> None:
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.data_manager = _FakeDataManager(connect_ok=False)
    ok = p.connect()
    assert ok is False


def test_connect_fails_if_any_service_fails() -> None:
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.data_manager = _FakeDataManager(connect_ok=True)
    p.blocking_service = _FakeService(ok=False)
    p.similarity_service = _FakeService(ok=True)
    p.clustering_service = _FakeService(ok=True)
    ok = p.connect()
    assert ok is False


def test_load_data_updates_pipeline_stats_on_success() -> None:
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.connected = True
    p.data_manager = _FakeDataManager(connect_ok=True)
    out = p.load_data(source="fake.json", collection_name="customers")
    assert out["success"] is True
    assert "data_quality" in out
    assert "data_loading" in p.pipeline_stats
    assert p.pipeline_stats["data_loading"]["records_loaded"] == 3


def test_setup_system_runs_collection_init_and_blocking_setup() -> None:
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.connected = True
    p.data_manager = _FakeDataManager()
    p.blocking_service = _FakeService(ok=True, setup_ok=True)
    out = p.setup_system(collections=["customers"])
    assert out["success"] is True
    assert "setup" in p.pipeline_stats


def test_run_entity_resolution_errors_if_no_records() -> None:
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.connected = True
    p.data_manager = _FakeDataManager(records=[])
    out = p.run_entity_resolution(collection_name="customers")
    assert out["success"] is False
    assert "no records" in out["error"].lower()


def test_run_entity_resolution_happy_path_compiles_results() -> None:
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.connected = True
    p.data_manager = _FakeDataManager(records=[{"_key": "1"}, {"_key": "2"}])

    p._run_blocking_stage = lambda records, collection_name: {"success": True, "candidate_pairs": [{"a": 1}]}  # type: ignore[assignment]
    p._run_similarity_stage = lambda candidate_pairs: {"success": True, "scored_pairs": [{"s": 1}]}  # type: ignore[assignment]
    p._run_clustering_stage = lambda scored_pairs, threshold: {"success": True, "clusters": [["1", "2"]]}  # type: ignore[assignment]

    out = p.run_entity_resolution(collection_name="customers", similarity_threshold=0.8)
    assert out["success"] is True
    assert out["input_records"] == 2
    assert out["candidate_pairs"] == 1
    assert out["scored_pairs"] == 1
    assert out["entity_clusters"] == 1
    assert "entity_resolution" in p.pipeline_stats


class _FakeBlockingServiceWithCandidates:
    """Blocking service stub that returns configurable candidates."""

    def __init__(self, candidates_by_id: dict):
        # Map target_record_id -> list of candidate dicts
        self._candidates = candidates_by_id

    def connect(self) -> bool:
        return True

    def generate_candidates(self, collection: str, target_record_id: str, **kwargs):
        candidates = self._candidates.get(target_record_id, [])
        return {"success": True, "candidates": candidates}


def test_run_blocking_stage_delegates_to_blocking_service() -> None:
    """_run_blocking_stage should call blocking_service.generate_candidates,
    not fall back to the old O(n²) Python loop."""
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.connected = True

    rec_a = {"_id": "col/1", "_key": "1", "first_name": "Alice"}
    rec_b = {"_id": "col/2", "_key": "2", "first_name": "Alicia"}

    # blocking service returns rec_b as a candidate for rec_a (and nothing for rec_b)
    p.blocking_service = _FakeBlockingServiceWithCandidates({
        "col/1": [{"_id": "col/2", "document": rec_b}],
        "col/2": [],
    })

    result = p._run_blocking_stage([rec_a, rec_b], "col")

    assert result["success"] is True
    assert len(result["candidate_pairs"]) == 1
    pair = result["candidate_pairs"][0]
    # Keys should be normalised: smaller lexicographically first
    assert pair["record_a_id"] <= pair["record_b_id"]


def test_run_blocking_stage_deduplicates_pairs() -> None:
    """Pairs found from multiple records should be deduplicated."""
    with pytest.warns(DeprecationWarning):
        p = EntityResolutionPipeline()
    p.connected = True

    rec_a = {"_id": "col/1", "_key": "1"}
    rec_b = {"_id": "col/2", "_key": "2"}

    # Both records discover each other — would yield (col/1,col/2) twice without dedup
    p.blocking_service = _FakeBlockingServiceWithCandidates({
        "col/1": [{"_id": "col/2", "document": rec_b}],
        "col/2": [{"_id": "col/1", "document": rec_a}],
    })

    result = p._run_blocking_stage([rec_a, rec_b], "col")

    assert result["success"] is True
    assert len(result["candidate_pairs"]) == 1


