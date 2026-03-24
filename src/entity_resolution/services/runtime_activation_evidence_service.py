"""
Helpers to summarize runtime matrix activation artifacts.

Used to convert runtime matrix outputs into a compact summary that can be
attached to self-hosted activation and baseline-rotation PRs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable


class RuntimeActivationEvidenceService:
    """Build machine-readable and markdown activation evidence summaries."""

    @staticmethod
    def summarize(
        artifacts_root: str,
        platforms: Iterable[str] = ("linux-cpu", "apple-silicon", "linux-gpu"),
    ) -> Dict[str, Any]:
        root = Path(artifacts_root)
        runtime_dir = root / "runtime"
        quality_dir = root / "quality"

        platform_summaries: Dict[str, Any] = {}
        for platform in platforms:
            env_path = runtime_dir / f"runtime_env_{platform}.json"
            env_payload = _load_json_if_exists(env_path)
            platform_summaries[platform] = {
                "runtime_env_path": str(env_path),
                "runtime_env_found": env_payload is not None,
                "runtime_env": env_payload,
            }

        quality_path = quality_dir / "quality_gate_linux-cpu.json"
        quality_payload = _load_json_if_exists(quality_path)
        registry_path = runtime_dir / "runtime_registry_linux-cpu.json"
        registry_payload = _load_json_if_exists(registry_path)

        quality_gate = None
        quality_regression = None
        current_source = None
        if isinstance(quality_payload, dict):
            quality_gate = quality_payload.get("quality_gate")
            if isinstance(quality_gate, dict):
                regressions = quality_gate.get("regressions", {})
                if isinstance(regressions, dict):
                    quality_regression = regressions.get("quality_regression")
                current_source = quality_gate.get("current_source")

        summary = {
            "platforms": platform_summaries,
            "linux_cpu_quality_gate": {
                "quality_gate_path": str(quality_path),
                "quality_gate_found": quality_payload is not None,
                "quality_gate_current_source": current_source,
                "quality_regression": quality_regression,
            },
            "linux_cpu_registry": {
                "registry_path": str(registry_path),
                "registry_found": registry_payload is not None,
            },
            "checklist": {
                "all_runtime_env_found": all(
                    item["runtime_env_found"] for item in platform_summaries.values()
                ),
                "linux_cpu_quality_gate_found": quality_payload is not None,
                "linux_cpu_registry_found": registry_payload is not None,
                "linux_cpu_quality_source_is_corpus": current_source == "corpus_benchmark",
                "linux_cpu_quality_regression": quality_regression,
            },
        }
        return summary

    @staticmethod
    def to_markdown(summary: Dict[str, Any]) -> str:
        checklist = summary.get("checklist", {})
        lines = [
            "## Runtime Matrix Activation Evidence",
            f"- Runtime env artifacts complete: {_mark(checklist.get('all_runtime_env_found'))}",
            (
                "- Linux CPU quality gate artifact: "
                f"{_mark(checklist.get('linux_cpu_quality_gate_found'))}"
            ),
            (
                "- Linux CPU registry artifact: "
                f"{_mark(checklist.get('linux_cpu_registry_found'))}"
            ),
            (
                "- Linux CPU quality source is corpus benchmark: "
                f"{_mark(checklist.get('linux_cpu_quality_source_is_corpus'))}"
            ),
        ]
        regression = checklist.get("linux_cpu_quality_regression")
        if regression is not None:
            lines.append(
                "- Linux CPU quality regression detected: "
                + ("yes" if regression else "no")
            )

        lines.append("")
        lines.append("### Runtime Environment Files")
        for platform, details in (summary.get("platforms") or {}).items():
            lines.append(
                f"- `{platform}`: {_mark(details.get('runtime_env_found'))} "
                f"({details.get('runtime_env_path')})"
            )
        return "\n".join(lines)


def _load_json_if_exists(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _mark(value: Any) -> str:
    return "yes" if bool(value) else "no"
