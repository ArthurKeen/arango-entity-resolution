from __future__ import annotations

import json
from pathlib import Path

from entity_resolution.services.runtime_quality_benchmark_service import (
    RuntimeQualityBenchmarkService,
)


def test_scaffold_corpus_creates_json(tmp_path: Path) -> None:
    target = tmp_path / "corpus.json"
    written = RuntimeQualityBenchmarkService.scaffold_corpus(str(target))
    assert written == str(target)
    payload = json.loads(target.read_text())
    assert "cosine_pairs" in payload
    assert "retrieval_queries" in payload


def test_run_benchmark_computes_cosine_drift_and_topk_overlap() -> None:
    corpus = {
        "metadata": {"name": "tiny"},
        "cosine_pairs": [
            {
                "id": "p1",
                "text_a": "A",
                "text_b": "A_similar",
                "expected_cosine": 1.0,
            }
        ],
        "retrieval_queries": [
            {
                "id": "q1",
                "query": "Q",
                "top_k": 2,
                "expected_topk": ["c1", "c2"],
                "candidates": [
                    {"id": "c1", "text": "A"},
                    {"id": "c2", "text": "A_similar"},
                    {"id": "c3", "text": "B"},
                ],
            }
        ],
    }

    vectors = {
        "Q": [1.0, 0.0],
        "A": [1.0, 0.0],
        "A_similar": [0.99, 0.01],
        "B": [0.0, 1.0],
    }

    def embed_texts(texts):
        return [vectors[text] for text in texts]

    result = RuntimeQualityBenchmarkService.run_benchmark(corpus=corpus, embed_texts=embed_texts)
    assert result["cosine_drift"] is not None
    assert result["cosine_drift"] < 0.001
    assert result["topk_overlap"] == 1.0


def test_write_metrics_file_writes_stable_path(tmp_path: Path) -> None:
    output_path = tmp_path / "baseline_metrics.json"
    written = RuntimeQualityBenchmarkService.write_metrics_file(
        metrics={"cosine_drift": 0.01, "topk_overlap": 0.95},
        output_path=str(output_path),
    )
    assert written == str(output_path)
    payload = json.loads(output_path.read_text())
    assert payload["cosine_drift"] == 0.01

