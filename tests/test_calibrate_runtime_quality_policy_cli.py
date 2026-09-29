"""The calibration CLI must actually run, not merely import.

This script shipped calling `RuntimeQualityPolicyCalibrationService.load_policy`,
a method that does not exist on that class. It raised AttributeError on the first
line of real work, so the documented way to regenerate a quality baseline could
never have worked. The service had unit tests and passed them all; nothing
executed the command those tests were supposed to make trustworthy.

That is the repository's signature defect — something built but never wired into
anything that exercises it — so the fix is a test that runs the CLI end to end
rather than one that pokes the service again.

The loop under test: a CI quality artifact goes in; a calibrated policy and an
updated baseline come out; and the policy service, which is what CI actually
gates on, still accepts the result. Any link breaking fails this.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from entity_resolution.services.runtime_quality_policy_service import (
    RuntimeQualityPolicyService,
)

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "calibrate_runtime_quality_policy.py"


def _fixture(tmp_path: Path, *, cosine: float, overlap: float) -> tuple[Path, Path]:
    """A policy, a baseline it points at, and a CI artifact to calibrate from."""
    baseline = tmp_path / "windows-cpu.json"
    baseline.write_text(json.dumps({
        "metadata": {"profile": "windows-cpu"},
        "cosine_drift": 0.09, "topk_overlap": 1.0,
    }))
    policy = tmp_path / "policy.json"

    def _profile(label: str) -> dict:
        return {
            "label": label,
            # The corpus must exist for the policy service to validate it.
            "quality_corpus": "ci/runtime-quality/corpus/runtime_quality_corpus.json",
            "quality_baseline_metrics": str(baseline),
            "quality_model_name": "all-MiniLM-L6-v2",
            "quality_device": "cpu",
            "quality_batch_size": 16,
            "quality_cosine_drift_max": 0.12,
            "quality_topk_overlap_min": 0.8,
        }

    # validate_policy_file requires every profile in REQUIRED_PROFILES, so a
    # fixture holding only the one under calibration cannot be re-validated.
    policy.write_text(json.dumps({
        "version": 1,
        "profiles": {
            "windows-cpu": _profile("ci-windows-cpu"),
            "linux-cpu": _profile("ci-linux-cpu"),
            "apple-silicon": _profile("ci-apple-silicon"),
            "linux-gpu": _profile("ci-linux-gpu"),
        },
    }))
    artifact = tmp_path / "quality_gate_windows-cpu.json"
    artifact.write_text(json.dumps(
        {"quality_gate": {"current_metrics": {
            "cosine_drift": cosine, "topk_overlap": overlap}}}
    ))
    return policy, artifact


def _run(policy: Path, artifact: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--policy", str(policy),
         "--calibration", f"windows-cpu={artifact}", *extra],
        cwd=REPO, capture_output=True, text=True,
    )


def test_cli_runs_and_reports_a_proposal(tmp_path: Path) -> None:
    """The regression: invoking the command must not blow up."""
    policy, artifact = _fixture(tmp_path, cosine=0.101234, overlap=0.97)

    proc = _run(policy, artifact)

    assert proc.returncode == 0, (
        f"the calibration CLI failed to run.\nstderr:\n{proc.stderr}"
    )
    report = json.loads(proc.stdout)
    assert report["write_applied"] is False, "a dry run must not write"
    change = report["changes"][0]
    assert change["profile"] == "windows-cpu"
    assert change["observed"]["cosine_drift"] == pytest.approx(0.101234)


def test_dry_run_leaves_the_policy_untouched(tmp_path: Path) -> None:
    policy, artifact = _fixture(tmp_path, cosine=0.101234, overlap=0.97)
    before = policy.read_text()

    _run(policy, artifact)

    assert policy.read_text() == before


def test_write_produces_a_policy_the_gate_still_accepts(tmp_path: Path) -> None:
    """The loop that matters: calibrate, then re-validate.

    A calibrated policy that the policy service rejects would break CI on the
    next run, which is the opposite of what re-baselining is for.
    """
    policy, artifact = _fixture(tmp_path, cosine=0.101234, overlap=0.97)
    before = json.loads(policy.read_text())

    proc = _run(policy, artifact, "--write", "--update-baselines")
    assert proc.returncode == 0, proc.stderr

    report = json.loads(proc.stdout)
    assert report["baselines_updated"], "--update-baselines wrote no baseline"

    # Assert the FILE changed, not the report's `write_applied` field: that field
    # is `bool(args.write)`, an echo of the flag rather than evidence of a write.
    # Trusting it let a mutation that disabled the write entirely pass this test.
    after = json.loads(policy.read_text())
    assert after != before, "--write reported success without changing the policy"
    thresholds = after["profiles"]["windows-cpu"]
    assert thresholds["quality_cosine_drift_max"] != \
        before["profiles"]["windows-cpu"]["quality_cosine_drift_max"]

    written = json.loads(Path(report["baselines_updated"][0]).read_text())
    assert written["cosine_drift"] == pytest.approx(0.101234)
    assert written["topk_overlap"] == pytest.approx(0.97)
    assert written["metadata"]["profile"] == "windows-cpu"

    # The gate must still accept what calibration produced.
    RuntimeQualityPolicyService.validate_policy_file(str(policy))


def test_thresholds_move_toward_the_observed_metrics(tmp_path: Path) -> None:
    """Calibration must respond to the artifact, not emit constants."""
    policy, artifact = _fixture(tmp_path, cosine=0.05, overlap=0.99)

    report = json.loads(_run(policy, artifact).stdout)
    after = report["changes"][0]["thresholds_after"]

    assert after["quality_cosine_drift_max"] < 0.12, (
        "a much lower observed drift must tighten the ceiling"
    )
    assert after["quality_topk_overlap_min"] > 0.8, (
        "a much higher observed overlap must raise the floor"
    )


def test_unknown_profile_is_rejected(tmp_path: Path) -> None:
    """Calibrating a profile the policy lacks is a mistake, not a silent no-op.

    A typo in a profile name would otherwise report success having changed
    nothing, and the operator would believe a baseline was rotated.
    """
    policy, artifact = _fixture(tmp_path, cosine=0.1, overlap=0.97)

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--policy", str(policy),
         "--calibration", f"no-such-profile={artifact}"],
        cwd=REPO, capture_output=True, text=True,
    )

    assert proc.returncode != 0
