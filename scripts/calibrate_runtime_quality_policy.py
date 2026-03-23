#!/usr/bin/env python3
"""
Calibrate runtime quality policy thresholds from CI artifacts.

Example:
  python scripts/calibrate_runtime_quality_policy.py \
    --policy ci/runtime-quality/quality_gate_policy.json \
    --calibration linux-cpu=artifacts/quality/quality_gate_linux-cpu.json \
    --write \
    --update-baselines
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from entity_resolution.services.runtime_quality_policy_calibration_service import (
    RuntimeQualityPolicyCalibrationService,
)


def _parse_calibration_entry(entry: str) -> tuple[str, str]:
    if "=" not in entry:
        raise argparse.ArgumentTypeError(
            f"Invalid calibration entry: {entry}. Expected <profile>=<artifact_path>."
        )
    profile, artifact = entry.split("=", 1)
    profile = profile.strip()
    artifact = artifact.strip()
    if not profile or not artifact:
        raise argparse.ArgumentTypeError(
            f"Invalid calibration entry: {entry}. Expected <profile>=<artifact_path>."
        )
    return profile, artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate runtime quality policy from quality gate artifacts."
    )
    parser.add_argument(
        "--policy",
        default="ci/runtime-quality/quality_gate_policy.json",
        help="Path to runtime quality policy JSON.",
    )
    parser.add_argument(
        "--calibration",
        action="append",
        required=True,
        help="Calibration mapping in form <profile>=<quality_gate_artifact_path>. Repeatable.",
    )
    parser.add_argument(
        "--cosine-headroom",
        type=float,
        default=0.02,
        help="Headroom added to observed cosine_drift when setting quality_cosine_drift_max.",
    )
    parser.add_argument(
        "--overlap-headroom",
        type=float,
        default=0.02,
        help="Headroom subtracted from observed topk_overlap when setting quality_topk_overlap_min.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write calibrated policy back to --policy file.",
    )
    parser.add_argument(
        "--update-baselines",
        action="store_true",
        help="Also update per-profile baseline metric files referenced by the policy.",
    )
    args = parser.parse_args()

    policy_path = Path(args.policy)
    policy = RuntimeQualityPolicyCalibrationService.load_policy(str(policy_path))

    profile_metrics: Dict[str, Dict[str, float]] = {}
    for entry in args.calibration:
        profile, artifact_path = _parse_calibration_entry(entry)
        profile_metrics[profile] = RuntimeQualityPolicyCalibrationService.load_artifact_metrics(
            artifact_path
        )

    calibrated_policy, changes = RuntimeQualityPolicyCalibrationService.calibrate_policy(
        policy=policy,
        profile_metrics=profile_metrics,
        cosine_headroom=args.cosine_headroom,
        overlap_headroom=args.overlap_headroom,
    )

    updated_baselines = []
    if args.update_baselines:
        updated_baselines = RuntimeQualityPolicyCalibrationService.update_baselines(
            calibrated_policy, profile_metrics
        )

    if args.write:
        policy_path.write_text(json.dumps(calibrated_policy, indent=2), encoding="utf-8")

    summary = {
        "policy_file": str(policy_path),
        "write_applied": bool(args.write),
        "baselines_updated": updated_baselines,
        "changes": changes,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
