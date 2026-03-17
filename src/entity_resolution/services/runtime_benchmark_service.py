"""
Runtime health benchmark helpers.

Provides a lightweight benchmark harness for repeated embedding runtime-health
checks and summary statistics for CI and release validation.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List


class RuntimeBenchmarkService:
    """Run repeated runtime-health probes and summarize latency/telemetry."""

    @staticmethod
    def run_benchmark(
        probe: Callable[[], Dict[str, Any]],
        repeats: int = 5,
    ) -> Dict[str, Any]:
        if repeats < 1:
            raise ValueError(f"repeats must be >= 1, got: {repeats}")

        runs: List[Dict[str, Any]] = []
        latencies: List[float] = []
        fallback_counts: List[int] = []

        for i in range(repeats):
            snapshot = probe()
            latency = _to_float(snapshot.get("setup_latency_ms"))
            fallback_count = _to_int((snapshot.get("telemetry") or {}).get("fallback_count"))

            runs.append(
                {
                    "run": i + 1,
                    "setup_latency_ms": latency,
                    "fallback_count": fallback_count,
                    "snapshot": snapshot,
                }
            )
            if latency is not None:
                latencies.append(latency)
            fallback_counts.append(fallback_count)

        summary = {
            "runs": repeats,
            "latency_ms": RuntimeBenchmarkService._latency_stats(latencies),
            "fallback": {
                "max_fallback_count": max(fallback_counts) if fallback_counts else 0,
                "total_fallback_events": sum(fallback_counts),
                "fallback_runs": sum(1 for count in fallback_counts if count > 0),
            },
        }

        return {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "repeats": repeats,
            },
            "summary": summary,
            "runs": runs,
        }

    @staticmethod
    def export_benchmark(
        benchmark_result: Dict[str, Any],
        output_dir: str,
        filename_prefix: str = "runtime_benchmark",
    ) -> str:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = output_path / f"{filename_prefix}_{timestamp}.json"
        json_path.write_text(json.dumps(benchmark_result, indent=2), encoding="utf-8")
        return str(json_path)

    @staticmethod
    def _latency_stats(latencies: List[float]) -> Dict[str, Any]:
        if not latencies:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "p95": None,
            }
        sorted_latencies = sorted(latencies)
        p95_index = max(0, int(round(0.95 * (len(sorted_latencies) - 1))))
        return {
            "count": len(sorted_latencies),
            "min": round(min(sorted_latencies), 2),
            "max": round(max(sorted_latencies), 2),
            "mean": round(statistics.mean(sorted_latencies), 2),
            "median": round(statistics.median(sorted_latencies), 2),
            "p95": round(sorted_latencies[p95_index], 2),
        }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

