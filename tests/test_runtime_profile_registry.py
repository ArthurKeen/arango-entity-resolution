from __future__ import annotations

from entity_resolution.services.runtime_profile_registry import RuntimeProfileRegistry


def _snapshot(latency_ms: float = 10.0, fallback_count: int = 0):
    return {
        "enabled": True,
        "runtime": "onnxruntime",
        "model_name": "bert-onnx",
        "resolved_provider": "cpu",
        "resolved_device": "na",
        "setup_latency_ms": latency_ms,
        "telemetry": {"fallback_count": fallback_count},
    }


def test_upsert_and_compare_snapshot(tmp_path) -> None:
    registry = tmp_path / "runtime_registry.json"

    baseline = RuntimeProfileRegistry.upsert_baseline(
        registry_file=str(registry),
        snapshot=_snapshot(latency_ms=10.0, fallback_count=0),
        label="dev",
    )
    assert baseline["label"] == "dev"

    comparison = RuntimeProfileRegistry.compare_snapshot(
        registry_file=str(registry),
        snapshot=_snapshot(latency_ms=11.0, fallback_count=0),
        label="dev",
        latency_regression_pct=20.0,
    )
    assert comparison["baseline_found"] is True
    assert comparison["comparison"]["latency_delta_ms"] == 1.0
    assert comparison["regressions"]["latency_regression"] is False
    assert comparison["regressions"]["fallback_regression"] is False


def test_compare_flags_regressions(tmp_path) -> None:
    registry = tmp_path / "runtime_registry.json"
    RuntimeProfileRegistry.upsert_baseline(
        registry_file=str(registry),
        snapshot=_snapshot(latency_ms=10.0, fallback_count=0),
        label="prod",
    )

    comparison = RuntimeProfileRegistry.compare_snapshot(
        registry_file=str(registry),
        snapshot=_snapshot(latency_ms=15.0, fallback_count=2),
        label="prod",
        latency_regression_pct=20.0,
    )
    assert comparison["baseline_found"] is True
    assert comparison["regressions"]["latency_regression"] is True
    assert comparison["regressions"]["fallback_regression"] is True


def test_compare_returns_not_found_for_missing_baseline(tmp_path) -> None:
    registry = tmp_path / "runtime_registry.json"
    comparison = RuntimeProfileRegistry.compare_snapshot(
        registry_file=str(registry),
        snapshot=_snapshot(),
        label="missing",
    )
    assert comparison["baseline_found"] is False

