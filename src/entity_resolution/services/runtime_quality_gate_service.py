"""
Runtime quality gate comparison helpers.

Compares current quality metrics against baseline metrics using configurable
thresholds. Intended as a scaffold for Phase 1 quality gating.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class RuntimeQualityGateService:
    """Utility helpers for quality-gate metric comparisons."""

    @staticmethod
    def load_metrics(path: str) -> Dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def compare_metrics(
        current: Dict[str, Any],
        baseline: Dict[str, Any],
        *,
        cosine_drift_max: float = 0.01,
        topk_overlap_min: float = 0.95,
    ) -> Dict[str, Any]:
        baseline_cosine = _to_float(baseline.get("cosine_drift"))
        current_cosine = _to_float(current.get("cosine_drift"))
        baseline_overlap = _to_float(baseline.get("topk_overlap"))
        current_overlap = _to_float(current.get("topk_overlap"))

        cosine_regression = False
        overlap_regression = False
        if current_cosine is not None:
            cosine_regression = current_cosine > cosine_drift_max
        if current_overlap is not None:
            overlap_regression = current_overlap < topk_overlap_min

        return {
            "baseline_found": True,
            "comparison_type": "quality",
            "baseline_metrics": baseline,
            "current_metrics": current,
            "comparison": {
                "baseline_cosine_drift": baseline_cosine,
                "current_cosine_drift": current_cosine,
                "baseline_topk_overlap": baseline_overlap,
                "current_topk_overlap": current_overlap,
            },
            "thresholds": {
                "cosine_drift_max": cosine_drift_max,
                "topk_overlap_min": topk_overlap_min,
            },
            "regressions": {
                "cosine_drift_regression": cosine_regression,
                "topk_overlap_regression": overlap_regression,
                "quality_regression": bool(cosine_regression or overlap_regression),
            },
        }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

