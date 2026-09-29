from __future__ import annotations

import json
from pathlib import Path

from entity_resolution.services.runtime_quality_policy_calibration_service import (
    RuntimeQualityPolicyCalibrationService,
)


def test_load_artifact_metrics_reads_runtime_health_gate_shape(tmp_path: Path) -> None:
    artifact = tmp_path / "quality_gate_linux-cpu.json"
    artifact.write_text(
        json.dumps(
            {
                "quality_gate": {
                    "current_metrics": {
                        "cosine_drift": 0.12,
                        "topk_overlap": 0.78,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    out = RuntimeQualityPolicyCalibrationService.load_artifact_metrics(str(artifact))
    assert out["cosine_drift"] == 0.12
    assert out["topk_overlap"] == 0.78


def test_calibrate_policy_applies_headroom_and_bounds() -> None:
    policy = {
        "version": 1,
        "profiles": {
            "linux-cpu": {
                "quality_cosine_drift_max": 0.2,
                "quality_topk_overlap_min": 0.5,
                "quality_batch_size": 16,
                "quality_corpus": "ci/runtime-quality/corpus/runtime_quality_corpus.json",
                "quality_baseline_metrics": "ci/runtime-quality/baselines/linux-cpu.json",
            }
        },
    }
    profile_metrics = {"linux-cpu": {"cosine_drift": 0.99, "topk_overlap": 0.01}}

    calibrated, changes = RuntimeQualityPolicyCalibrationService.calibrate_policy(
        policy,
        profile_metrics,
        cosine_headroom=0.1,
        overlap_headroom=0.1,
    )

    cfg = calibrated["profiles"]["linux-cpu"]
    assert cfg["quality_cosine_drift_max"] == 1.0
    assert cfg["quality_topk_overlap_min"] == 0.0
    assert len(changes) == 1
    assert changes[0]["profile"] == "linux-cpu"


def test_update_baselines_writes_observed_metrics(tmp_path: Path) -> None:
    baseline = tmp_path / "linux-cpu.json"
    policy = {
        "version": 1,
        "profiles": {
            "linux-cpu": {
                "quality_baseline_metrics": str(baseline),
                "quality_batch_size": 16,
                "quality_corpus": "ci/runtime-quality/corpus/runtime_quality_corpus.json",
                "quality_cosine_drift_max": 0.2,
                "quality_topk_overlap_min": 0.5,
            }
        },
    }
    profile_metrics = {"linux-cpu": {"cosine_drift": 0.1234567, "topk_overlap": 0.7654321}}

    updated = RuntimeQualityPolicyCalibrationService.update_baselines(policy, profile_metrics)
    assert updated == [str(baseline)]

    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["metadata"]["profile"] == "linux-cpu"
    assert payload["cosine_drift"] == 0.123457
    assert payload["topk_overlap"] == 0.765432
