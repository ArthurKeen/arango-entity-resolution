from __future__ import annotations

from entity_resolution.services.runtime_quality_gate_service import RuntimeQualityGateService


def test_compare_metrics_no_regression() -> None:
    current = {"cosine_drift": 0.005, "topk_overlap": 0.98}
    baseline = {"cosine_drift": 0.003, "topk_overlap": 0.99}
    out = RuntimeQualityGateService.compare_metrics(
        current=current,
        baseline=baseline,
        cosine_drift_max=0.01,
        topk_overlap_min=0.95,
    )
    assert out["regressions"]["quality_regression"] is False
    assert out["regressions"]["cosine_drift_regression"] is False
    assert out["regressions"]["topk_overlap_regression"] is False


def test_compare_metrics_detects_regression() -> None:
    current = {"cosine_drift": 0.02, "topk_overlap": 0.9}
    baseline = {"cosine_drift": 0.003, "topk_overlap": 0.99}
    out = RuntimeQualityGateService.compare_metrics(
        current=current,
        baseline=baseline,
        cosine_drift_max=0.01,
        topk_overlap_min=0.95,
    )
    assert out["regressions"]["quality_regression"] is True
    assert out["regressions"]["cosine_drift_regression"] is True
    assert out["regressions"]["topk_overlap_regression"] is True

