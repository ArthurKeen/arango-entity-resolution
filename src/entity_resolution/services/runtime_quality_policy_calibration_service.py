"""
Helpers to calibrate runtime quality policy from CI artifacts.

This module turns `runtime-health-gate` quality artifacts into policy threshold
updates so profile thresholds can be tuned with less manual editing.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List


class RuntimeQualityPolicyCalibrationService:
    """Calibrate policy thresholds from runtime quality artifacts."""

    @staticmethod
    def load_artifact_metrics(artifact_path: str) -> Dict[str, float]:
        payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        quality_block = payload.get("quality_gate") if isinstance(payload, dict) else None
        if isinstance(quality_block, dict):
            metrics = quality_block.get("current_metrics", {})
        else:
            metrics = payload.get("current_metrics", {}) if isinstance(payload, dict) else {}

        cosine = _to_float(metrics.get("cosine_drift"))
        overlap = _to_float(metrics.get("topk_overlap"))
        if cosine is None or overlap is None:
            raise ValueError(
                f"Artifact {artifact_path} is missing quality metrics: "
                "current_metrics.cosine_drift/topk_overlap"
            )

        return {"cosine_drift": cosine, "topk_overlap": overlap}

    @staticmethod
    def calibrate_policy(
        policy: Dict[str, Any],
        profile_metrics: Dict[str, Dict[str, float]],
        *,
        cosine_headroom: float = 0.02,
        overlap_headroom: float = 0.02,
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        updated = copy.deepcopy(policy)
        profiles = updated.get("profiles")
        if not isinstance(profiles, dict):
            raise ValueError("Policy must contain an object 'profiles'.")

        changes: List[Dict[str, Any]] = []
        for profile, metrics in profile_metrics.items():
            if profile not in profiles:
                raise ValueError(f"Profile {profile} not found in policy.")

            cosine = metrics["cosine_drift"]
            overlap = metrics["topk_overlap"]
            proposed_cosine_max = _clamp_01(cosine + cosine_headroom)
            proposed_overlap_min = _clamp_01(overlap - overlap_headroom)

            profile_cfg = profiles[profile]
            before_cosine = _to_float(profile_cfg.get("quality_cosine_drift_max"))
            before_overlap = _to_float(profile_cfg.get("quality_topk_overlap_min"))
            profile_cfg["quality_cosine_drift_max"] = round(proposed_cosine_max, 6)
            profile_cfg["quality_topk_overlap_min"] = round(proposed_overlap_min, 6)

            changes.append(
                {
                    "profile": profile,
                    "observed": {
                        "cosine_drift": cosine,
                        "topk_overlap": overlap,
                    },
                    "thresholds_before": {
                        "quality_cosine_drift_max": before_cosine,
                        "quality_topk_overlap_min": before_overlap,
                    },
                    "thresholds_after": {
                        "quality_cosine_drift_max": profile_cfg["quality_cosine_drift_max"],
                        "quality_topk_overlap_min": profile_cfg["quality_topk_overlap_min"],
                    },
                }
            )

        return updated, changes

    @staticmethod
    def update_baselines(
        policy: Dict[str, Any],
        profile_metrics: Dict[str, Dict[str, float]],
    ) -> List[str]:
        profiles = policy.get("profiles")
        if not isinstance(profiles, dict):
            raise ValueError("Policy must contain an object 'profiles'.")

        updated_files: List[str] = []
        for profile, metrics in profile_metrics.items():
            if profile not in profiles:
                raise ValueError(f"Profile {profile} not found in policy.")
            baseline_path = profiles[profile].get("quality_baseline_metrics")
            if not baseline_path:
                raise ValueError(
                    f"Profile {profile} missing quality_baseline_metrics path in policy."
                )

            path = Path(str(baseline_path))
            payload: Dict[str, Any] = {}
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
            payload.setdefault("metadata", {})
            payload["metadata"]["profile"] = profile
            payload["cosine_drift"] = round(metrics["cosine_drift"], 6)
            payload["topk_overlap"] = round(metrics["topk_overlap"], 6)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            updated_files.append(str(path))
        return updated_files


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, value))
