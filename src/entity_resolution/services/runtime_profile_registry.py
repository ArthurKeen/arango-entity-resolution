"""
Runtime profile registry for embedding health snapshots.

Stores baseline snapshots and compares new snapshots against historical
baselines by runtime/model/provider key.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class RuntimeProfileRegistry:
    """Persist and compare runtime health baselines."""

    REGISTRY_VERSION = 1

    @classmethod
    def load(cls, registry_file: str) -> Dict[str, Any]:
        path = Path(registry_file)
        if not path.exists():
            return {
                "version": cls.REGISTRY_VERSION,
                "baselines": [],
            }
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def save(cls, registry_file: str, payload: Dict[str, Any]) -> None:
        path = Path(registry_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def upsert_baseline(
        cls,
        registry_file: str,
        snapshot: Dict[str, Any],
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = cls.load(registry_file)
        baselines: List[Dict[str, Any]] = list(payload.get("baselines", []))

        key = cls._baseline_key(snapshot, label=label)
        entry = {
            "key": key,
            "label": label,
            "recorded_at": datetime.utcnow().isoformat(),
            "snapshot": snapshot,
        }

        replaced = False
        for idx, existing in enumerate(baselines):
            if existing.get("key") == key:
                baselines[idx] = entry
                replaced = True
                break
        if not replaced:
            baselines.append(entry)

        payload["version"] = cls.REGISTRY_VERSION
        payload["baselines"] = baselines
        cls.save(registry_file, payload)
        return entry

    @classmethod
    def compare_snapshot(
        cls,
        registry_file: str,
        snapshot: Dict[str, Any],
        label: Optional[str] = None,
        latency_regression_pct: float = 20.0,
    ) -> Dict[str, Any]:
        payload = cls.load(registry_file)
        baselines: List[Dict[str, Any]] = list(payload.get("baselines", []))
        key = cls._baseline_key(snapshot, label=label)

        baseline = next((entry for entry in baselines if entry.get("key") == key), None)
        if baseline is None:
            return {
                "baseline_found": False,
                "key": key,
                "snapshot": snapshot,
                "message": "No matching baseline found for snapshot key",
            }

        baseline_snapshot = baseline.get("snapshot", {})
        current_latency = cls._safe_float(snapshot.get("setup_latency_ms"))
        baseline_latency = cls._safe_float(baseline_snapshot.get("setup_latency_ms"))
        baseline_fallback = cls._safe_int(
            (baseline_snapshot.get("telemetry") or {}).get("fallback_count")
        )
        current_fallback = cls._safe_int(
            (snapshot.get("telemetry") or {}).get("fallback_count")
        )

        latency_delta_ms = None
        latency_delta_pct = None
        latency_regression = False
        if current_latency is not None and baseline_latency is not None:
            latency_delta_ms = round(current_latency - baseline_latency, 1)
            if baseline_latency > 0:
                latency_delta_pct = round((latency_delta_ms / baseline_latency) * 100, 2)
                latency_regression = latency_delta_pct > latency_regression_pct

        fallback_regression = current_fallback > baseline_fallback

        return {
            "baseline_found": True,
            "key": key,
            "baseline": baseline_snapshot,
            "snapshot": snapshot,
            "comparison": {
                "latency_baseline_ms": baseline_latency,
                "latency_current_ms": current_latency,
                "latency_delta_ms": latency_delta_ms,
                "latency_delta_pct": latency_delta_pct,
                "fallback_baseline_count": baseline_fallback,
                "fallback_current_count": current_fallback,
            },
            "regressions": {
                "latency_regression": latency_regression,
                "fallback_regression": fallback_regression,
            },
            "thresholds": {
                "latency_regression_pct": latency_regression_pct,
            },
        }

    @staticmethod
    def _baseline_key(snapshot: Dict[str, Any], label: Optional[str] = None) -> str:
        parts = [
            label or "default",
            str(snapshot.get("runtime") or "unknown"),
            str(snapshot.get("model_name") or "unknown"),
            str(snapshot.get("resolved_provider") or "unknown"),
            str(snapshot.get("resolved_device") or "na"),
        ]
        return "|".join(parts)

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

