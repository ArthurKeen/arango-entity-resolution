from __future__ import annotations

import csv
import json
from pathlib import Path

from entity_resolution.services.runtime_compare_report_service import RuntimeCompareReportService


def _comparison_payload():
    return {
        "baseline_found": True,
        "key": "dev|onnxruntime|bert|cpu|na",
        "comparison": {
            "latency_baseline_ms": 10.0,
            "latency_current_ms": 12.0,
            "latency_delta_ms": 2.0,
            "latency_delta_pct": 20.0,
            "fallback_baseline_count": 0,
            "fallback_current_count": 1,
        },
        "regressions": {
            "latency_regression": False,
            "fallback_regression": True,
        },
    }


def test_export_report_writes_json_md_csv(tmp_path: Path) -> None:
    output_files = RuntimeCompareReportService.export_report(
        comparison=_comparison_payload(),
        output_dir=str(tmp_path),
        filename_prefix="cmp",
    )
    assert Path(output_files["json"]).exists()
    assert Path(output_files["markdown"]).exists()
    assert Path(output_files["csv"]).exists()

    json_payload = json.loads(Path(output_files["json"]).read_text(encoding="utf-8"))
    assert json_payload["baseline_found"] is True

    md_content = Path(output_files["markdown"]).read_text(encoding="utf-8")
    assert "Runtime Health Comparison" in md_content
    assert "Fallback regression: True" in md_content

    with Path(output_files["csv"]).open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["fallback_regression"] in ("True", "true", "1")


def test_markdown_for_missing_baseline() -> None:
    md = RuntimeCompareReportService._to_markdown(
        {
            "baseline_found": False,
            "key": "missing",
            "message": "No matching baseline found",
        }
    )
    assert "Baseline found: False" in md
    assert "No matching baseline found" in md


def test_markdown_uses_quality_title_for_quality_comparison() -> None:
    md = RuntimeCompareReportService._to_markdown(
        {
            "comparison_type": "quality",
            "baseline_found": True,
            "key": "k",
            "comparison": {},
            "regressions": {},
        }
    )
    assert "# Runtime Quality Comparison" in md

