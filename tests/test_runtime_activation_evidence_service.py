from __future__ import annotations

import json
from pathlib import Path

from entity_resolution.services.runtime_activation_evidence_service import (
    RuntimeActivationEvidenceService,
)


def test_summarize_detects_expected_artifacts(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    quality_dir = tmp_path / "quality"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    quality_dir.mkdir(parents=True, exist_ok=True)

    for platform in ("linux-cpu", "apple-silicon", "linux-gpu"):
        (runtime_dir / f"runtime_env_{platform}.json").write_text(
            json.dumps({"platform_tag": platform}),
            encoding="utf-8",
        )

    (runtime_dir / "runtime_registry_linux-cpu.json").write_text(
        json.dumps({"version": 1, "baselines": []}),
        encoding="utf-8",
    )
    (quality_dir / "quality_gate_linux-cpu.json").write_text(
        json.dumps(
            {
                "quality_gate": {
                    "current_source": "corpus_benchmark",
                    "regressions": {"quality_regression": False},
                }
            }
        ),
        encoding="utf-8",
    )

    summary = RuntimeActivationEvidenceService.summarize(str(tmp_path))
    assert summary["checklist"]["all_runtime_env_found"] is True
    assert summary["checklist"]["linux_cpu_quality_gate_found"] is True
    assert summary["checklist"]["linux_cpu_registry_found"] is True
    assert summary["checklist"]["linux_cpu_quality_source_is_corpus"] is True
    assert summary["checklist"]["linux_cpu_quality_regression"] is False


def test_summarize_handles_missing_artifacts() -> None:
    summary = RuntimeActivationEvidenceService.summarize("does-not-exist")
    assert summary["checklist"]["all_runtime_env_found"] is False
    assert summary["checklist"]["linux_cpu_quality_gate_found"] is False
    assert summary["checklist"]["linux_cpu_registry_found"] is False


def test_to_markdown_renders_checklist_lines(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for platform in ("linux-cpu", "apple-silicon", "linux-gpu"):
        (runtime_dir / f"runtime_env_{platform}.json").write_text(
            json.dumps({"platform_tag": platform}),
            encoding="utf-8",
        )

    summary = RuntimeActivationEvidenceService.summarize(str(tmp_path))
    markdown = RuntimeActivationEvidenceService.to_markdown(summary)
    assert "## Runtime Matrix Activation Evidence" in markdown
    assert "`linux-cpu`" in markdown
