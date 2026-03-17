"""
Runtime quality benchmark corpus + metrics helpers.

Builds quality metrics artifacts from a small benchmark corpus:
- cosine drift against expected pairwise similarity
- top-k overlap against expected retrieval rankings
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence


class RuntimeQualityBenchmarkService:
    """Helpers for quality benchmark corpus lifecycle and metric generation."""

    @staticmethod
    def scaffold_corpus(path: str, overwrite: bool = False) -> str:
        target = Path(path)
        if target.exists() and not overwrite:
            raise FileExistsError(
                f"Corpus file already exists: {target}. Use overwrite=True to replace it."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": {
                "name": "sample_runtime_quality_corpus",
                "description": (
                    "Replace sample texts and expected values with your production "
                    "benchmark set before using this for gating."
                ),
            },
            "cosine_pairs": [
                {
                    "id": "pair_1",
                    "text_a": "Acme Corporation 123 Main Street New York NY",
                    "text_b": "Acme Corp 123 Main St New York New York",
                    "expected_cosine": 0.98,
                },
                {
                    "id": "pair_2",
                    "text_a": "Globex LLC 11 Elm Road Austin TX",
                    "text_b": "Initech 99 Market Street San Francisco CA",
                    "expected_cosine": 0.10,
                },
            ],
            "retrieval_queries": [
                {
                    "id": "query_1",
                    "query": "Acme Corp New York 123 Main",
                    "top_k": 2,
                    "expected_topk": ["c1", "c2"],
                    "candidates": [
                        {
                            "id": "c1",
                            "text": "Acme Corporation 123 Main Street New York NY",
                        },
                        {
                            "id": "c2",
                            "text": "Acme Corp 123 Main St New York New York",
                        },
                        {
                            "id": "c3",
                            "text": "Other Company 44 Sunset Blvd Los Angeles CA",
                        },
                    ],
                }
            ],
        }
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(target)

    @staticmethod
    def load_corpus(path: str) -> Dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def run_benchmark(
        corpus: Dict[str, Any],
        embed_texts: Callable[[List[str]], Sequence[Sequence[float]]],
    ) -> Dict[str, Any]:
        cosine_pairs = corpus.get("cosine_pairs", []) or []
        retrieval_queries = corpus.get("retrieval_queries", []) or []

        pair_results: List[Dict[str, Any]] = []
        pair_drifts: List[float] = []
        for pair in cosine_pairs:
            text_a = pair.get("text_a")
            text_b = pair.get("text_b")
            if not text_a or not text_b:
                continue
            vectors = embed_texts([str(text_a), str(text_b)])
            observed = _cosine_similarity(vectors[0], vectors[1])
            expected = _to_float(pair.get("expected_cosine"))
            drift = abs(observed - expected) if expected is not None else None
            if drift is not None:
                pair_drifts.append(drift)
            pair_results.append(
                {
                    "id": pair.get("id"),
                    "expected_cosine": expected,
                    "observed_cosine": round(observed, 6),
                    "absolute_drift": round(drift, 6) if drift is not None else None,
                }
            )

        retrieval_results: List[Dict[str, Any]] = []
        overlaps: List[float] = []
        for query in retrieval_queries:
            query_text = query.get("query")
            candidates = query.get("candidates", []) or []
            if not query_text or not candidates:
                continue

            query_vec = embed_texts([str(query_text)])[0]
            scored_candidates: List[Dict[str, Any]] = []
            for candidate in candidates:
                candidate_id = candidate.get("id")
                candidate_text = candidate.get("text")
                if not candidate_id or not candidate_text:
                    continue
                candidate_vec = embed_texts([str(candidate_text)])[0]
                score = _cosine_similarity(query_vec, candidate_vec)
                scored_candidates.append(
                    {"id": str(candidate_id), "score": round(score, 6)}
                )

            scored_candidates.sort(key=lambda row: row["score"], reverse=True)
            expected_topk = [str(item) for item in (query.get("expected_topk", []) or [])]
            top_k = _to_int(query.get("top_k")) or len(expected_topk) or 1
            predicted_topk = [row["id"] for row in scored_candidates[:top_k]]

            overlap = None
            if expected_topk:
                overlap = len(set(predicted_topk).intersection(expected_topk)) / len(
                    expected_topk
                )
                overlaps.append(overlap)

            retrieval_results.append(
                {
                    "id": query.get("id"),
                    "expected_topk": expected_topk,
                    "predicted_topk": predicted_topk,
                    "topk_overlap": round(overlap, 6) if overlap is not None else None,
                }
            )

        cosine_drift = (sum(pair_drifts) / len(pair_drifts)) if pair_drifts else None
        topk_overlap = (sum(overlaps) / len(overlaps)) if overlaps else None

        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "corpus_name": (corpus.get("metadata") or {}).get("name"),
                "pairs_evaluated": len(pair_results),
                "queries_evaluated": len(retrieval_results),
            },
            "cosine_drift": round(cosine_drift, 6) if cosine_drift is not None else None,
            "topk_overlap": round(topk_overlap, 6) if topk_overlap is not None else None,
            "details": {
                "pairs": pair_results,
                "retrieval": retrieval_results,
            },
        }

    @staticmethod
    def export_metrics(
        metrics: Dict[str, Any],
        output_dir: str,
        filename_prefix: str = "runtime_quality_metrics",
    ) -> str:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = output_path / f"{filename_prefix}_{timestamp}.json"
        json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return str(json_path)

    @staticmethod
    def write_metrics_file(
        metrics: Dict[str, Any],
        output_path: str,
        overwrite: bool = True,
    ) -> str:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not overwrite:
            raise FileExistsError(
                f"Metrics file already exists: {target}. Use overwrite=True to replace it."
            )
        target.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return str(target)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    denom = _norm(a) * _norm(b)
    if denom == 0:
        return 0.0
    return _dot(a, b) / denom


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
