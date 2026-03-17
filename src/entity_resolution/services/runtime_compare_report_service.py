"""
Runtime health comparison artifact export helpers.

Writes comparison outputs as JSON, Markdown, and CSV summaries suitable for
release artifacts and human review.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class RuntimeCompareReportService:
    """Export runtime-compare results in multiple artifact formats."""

    @staticmethod
    def export_report(
        comparison: Dict[str, Any],
        output_dir: str,
        filename_prefix: str = "runtime_compare",
    ) -> Dict[str, str]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = output_path / f"{filename_prefix}_{timestamp}.json"
        md_path = output_path / f"{filename_prefix}_{timestamp}.md"
        csv_path = output_path / f"{filename_prefix}_{timestamp}.csv"

        json_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        md_path.write_text(
            RuntimeCompareReportService._to_markdown(comparison),
            encoding="utf-8",
        )
        RuntimeCompareReportService._to_csv(comparison, csv_path)

        return {
            "json": str(json_path),
            "markdown": str(md_path),
            "csv": str(csv_path),
        }

    @staticmethod
    def _to_markdown(comparison: Dict[str, Any]) -> str:
        comparison_type = str(comparison.get("comparison_type") or "health")
        title = (
            "Runtime Quality Comparison"
            if comparison_type == "quality"
            else "Runtime Health Comparison"
        )
        baseline_found = bool(comparison.get("baseline_found"))
        regressions = comparison.get("regressions", {})
        comp = comparison.get("comparison", {})

        lines = [
            f"# {title}",
            "",
            f"- Baseline found: {baseline_found}",
            f"- Key: {comparison.get('key', 'n/a')}",
        ]
        if not baseline_found:
            lines.extend(["", comparison.get("message", "No baseline found.")])
            return "\n".join(lines) + "\n"

        lines.extend(
            [
                "",
                "## Metrics",
                "",
                f"- Baseline latency (ms): {comp.get('latency_baseline_ms')}",
                f"- Current latency (ms): {comp.get('latency_current_ms')}",
                f"- Latency delta (ms): {comp.get('latency_delta_ms')}",
                f"- Latency delta (%): {comp.get('latency_delta_pct')}",
                f"- Baseline fallback count: {comp.get('fallback_baseline_count')}",
                f"- Current fallback count: {comp.get('fallback_current_count')}",
                "",
                "## Regression Flags",
                "",
                f"- Latency regression: {bool(regressions.get('latency_regression'))}",
                f"- Fallback regression: {bool(regressions.get('fallback_regression'))}",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _to_csv(comparison: Dict[str, Any], csv_path: Path) -> None:
        comp = comparison.get("comparison", {})
        regressions = comparison.get("regressions", {})
        row = {
            "key": comparison.get("key"),
            "baseline_found": comparison.get("baseline_found"),
            "latency_baseline_ms": comp.get("latency_baseline_ms"),
            "latency_current_ms": comp.get("latency_current_ms"),
            "latency_delta_ms": comp.get("latency_delta_ms"),
            "latency_delta_pct": comp.get("latency_delta_pct"),
            "fallback_baseline_count": comp.get("fallback_baseline_count"),
            "fallback_current_count": comp.get("fallback_current_count"),
            "latency_regression": regressions.get("latency_regression"),
            "fallback_regression": regressions.get("fallback_regression"),
        }
        fieldnames = list(row.keys())
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(row)

