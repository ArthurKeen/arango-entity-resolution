"""
Supported CLI-facing runner for blocking A/B evaluation.

Promotes the existing ABEvaluationHarness into one reproducible workflow:
exact blocking as the baseline and BM25 blocking as the comparison strategy.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from arango.database import StandardDatabase

from ..strategies.bm25_blocking import BM25BlockingStrategy
from ..strategies.collect_blocking import CollectBlockingStrategy
from .ab_evaluation_harness import ABEvaluationHarness


class _StaticDatabaseManager:
    """Minimal adapter so the harness can reuse an existing DB handle."""

    def __init__(self, db: StandardDatabase):
        self._db = db

    def get_database(self, database_name: Optional[str] = None) -> StandardDatabase:
        return self._db


def load_ground_truth(ground_truth_path: str) -> List[Dict[str, Any]]:
    """Load ground-truth pairs from JSON or CSV."""
    path = Path(ground_truth_path)
    suffix = path.suffix.lower()

    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("pairs", [])
        if not isinstance(data, list):
            raise ValueError("Ground truth JSON must be a list or contain a top-level 'pairs' list")
        return data

    if suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows: List[Dict[str, Any]] = []
            for row in reader:
                rows.append(
                    {
                        "record_a_id": row.get("record_a_id"),
                        "record_b_id": row.get("record_b_id"),
                        "is_match": _parse_bool(row.get("is_match")),
                    }
                )
            return rows

    raise ValueError("Ground truth file must be .json or .csv")


def run_blocking_benchmark(
    *,
    db: StandardDatabase,
    collection_name: str,
    ground_truth_path: str,
    baseline_fields: Sequence[str],
    search_view: str,
    search_field: str,
    output_dir: str,
    filename_prefix: str = "blocking_benchmark",
    blocking_field: Optional[str] = None,
    baseline_max_block_size: int = 100,
    hybrid_bm25_threshold: float = 2.0,
    hybrid_limit_per_entity: int = 20,
) -> Dict[str, Any]:
    """Run the supported exact-vs-BM25 blocking benchmark workflow."""
    if not baseline_fields:
        raise ValueError("baseline_fields must contain at least one exact blocking field")

    ground_truth = load_ground_truth(ground_truth_path)
    db_manager = _StaticDatabaseManager(db)
    harness = ABEvaluationHarness(
        db_manager=db_manager,
        collection_name=collection_name,
        ground_truth=ground_truth,
    )

    def baseline_strategy() -> List[Dict[str, Any]]:
        strategy = CollectBlockingStrategy(
            db=db,
            collection=collection_name,
            blocking_fields=list(baseline_fields),
            max_block_size=baseline_max_block_size,
        )
        return strategy.generate_candidates()

    def hybrid_strategy() -> List[Dict[str, Any]]:
        strategy = BM25BlockingStrategy(
            db=db,
            collection=collection_name,
            search_view=search_view,
            search_field=search_field,
            blocking_field=blocking_field,
            bm25_threshold=hybrid_bm25_threshold,
            limit_per_entity=hybrid_limit_per_entity,
        )
        return strategy.generate_candidates()

    results = harness.evaluate(
        baseline_strategy=baseline_strategy,
        hybrid_strategy=hybrid_strategy,
    )
    output_files = harness.save_results(
        results,
        output_dir=output_dir,
        filename_prefix=filename_prefix,
    )
    results["output_files"] = output_files
    return results


def _parse_bool(value: Any) -> bool:
    """Parse boolean-like CSV values."""
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean value for is_match: {value}")
