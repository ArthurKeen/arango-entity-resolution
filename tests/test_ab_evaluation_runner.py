from __future__ import annotations

import json
from pathlib import Path

import pytest

from entity_resolution.services.ab_evaluation_runner import load_ground_truth, run_blocking_benchmark


def test_load_ground_truth_from_json_list(tmp_path: Path) -> None:
    path = tmp_path / "gt.json"
    path.write_text(json.dumps([{"record_a_id": "1", "record_b_id": "2", "is_match": True}]))

    rows = load_ground_truth(str(path))

    assert rows == [{"record_a_id": "1", "record_b_id": "2", "is_match": True}]


def test_load_ground_truth_from_csv(tmp_path: Path) -> None:
    path = tmp_path / "gt.csv"
    path.write_text("record_a_id,record_b_id,is_match\n1,2,true\n3,4,false\n", encoding="utf-8")

    rows = load_ground_truth(str(path))

    assert rows[0]["is_match"] is True
    assert rows[1]["is_match"] is False


def test_load_ground_truth_rejects_unknown_extension(tmp_path: Path) -> None:
    path = tmp_path / "gt.txt"
    path.write_text("nope", encoding="utf-8")

    with pytest.raises(ValueError, match=".json or .csv"):
        load_ground_truth(str(path))


def test_run_blocking_benchmark_uses_harness_and_saves_results(tmp_path: Path, monkeypatch) -> None:
    ground_truth = tmp_path / "gt.json"
    ground_truth.write_text(json.dumps([{"record_a_id": "1", "record_b_id": "2", "is_match": True}]))

    class FakeHarness:
        init_kwargs = None
        evaluate_called = False
        saved = None

        def __init__(self, **kwargs):
            FakeHarness.init_kwargs = kwargs

        def evaluate(self, baseline_strategy, hybrid_strategy):
            FakeHarness.evaluate_called = True
            baseline_pairs = baseline_strategy()
            hybrid_pairs = hybrid_strategy()
            assert baseline_pairs == [{"doc1_key": "a", "doc2_key": "b"}]
            assert hybrid_pairs == [{"doc1_key": "a", "doc2_key": "c"}]
            return {"baseline": {"precision": 0.8}, "hybrid": {"precision": 0.9}, "improvements": {}}

        def save_results(self, results, output_dir, filename_prefix):
            FakeHarness.saved = {
                "results": results,
                "output_dir": output_dir,
                "filename_prefix": filename_prefix,
            }
            return {"json": "out.json", "csv": "out.csv"}

    class FakeCollectBlockingStrategy:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def generate_candidates(self):
            return [{"doc1_key": "a", "doc2_key": "b"}]

    class FakeBM25BlockingStrategy:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def generate_candidates(self):
            return [{"doc1_key": "a", "doc2_key": "c"}]

    monkeypatch.setattr("entity_resolution.services.ab_evaluation_runner.ABEvaluationHarness", FakeHarness)
    monkeypatch.setattr("entity_resolution.services.ab_evaluation_runner.CollectBlockingStrategy", FakeCollectBlockingStrategy)
    monkeypatch.setattr("entity_resolution.services.ab_evaluation_runner.BM25BlockingStrategy", FakeBM25BlockingStrategy)

    result = run_blocking_benchmark(
        db=object(),
        collection_name="companies",
        ground_truth_path=str(ground_truth),
        baseline_fields=["name"],
        search_view="companies_search",
        search_field="name",
        output_dir=str(tmp_path),
    )

    assert FakeHarness.init_kwargs["collection_name"] == "companies"
    assert FakeHarness.evaluate_called is True
    assert FakeHarness.saved["filename_prefix"] == "blocking_benchmark"
    assert result["output_files"] == {"json": "out.json", "csv": "out.csv"}


def test_run_blocking_benchmark_requires_baseline_fields(tmp_path: Path) -> None:
    ground_truth = tmp_path / "gt.json"
    ground_truth.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="baseline_fields"):
        run_blocking_benchmark(
            db=object(),
            collection_name="companies",
            ground_truth_path=str(ground_truth),
            baseline_fields=[],
            search_view="companies_search",
            search_field="name",
            output_dir=str(tmp_path),
        )
