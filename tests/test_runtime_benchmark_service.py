from __future__ import annotations

from entity_resolution.services.runtime_benchmark_service import RuntimeBenchmarkService


def test_run_benchmark_summarizes_latency_and_fallback() -> None:
    samples = [
        {"setup_latency_ms": 10.0, "telemetry": {"fallback_count": 0}},
        {"setup_latency_ms": 20.0, "telemetry": {"fallback_count": 1}},
        {"setup_latency_ms": 30.0, "telemetry": {"fallback_count": 0}},
    ]
    idx = {"i": 0}

    def probe():
        value = samples[idx["i"]]
        idx["i"] += 1
        return value

    result = RuntimeBenchmarkService.run_benchmark(probe=probe, repeats=3)
    assert result["metadata"]["profile"] == "default"
    assert result["summary"]["latency_ms"]["count"] == 3
    assert result["summary"]["latency_ms"]["mean"] == 20.0
    assert result["summary"]["latency_ms"]["median"] == 20.0
    assert result["summary"]["fallback"]["fallback_runs"] == 1
    assert result["summary"]["fallback"]["total_fallback_events"] == 1


def test_run_benchmark_rejects_invalid_repeats() -> None:
    def probe():
        return {}

    try:
        RuntimeBenchmarkService.run_benchmark(probe=probe, repeats=0)
        assert False, "Expected ValueError for repeats=0"
    except ValueError as exc:
        assert "repeats must be" in str(exc)


def test_run_benchmark_excludes_warmup_runs_from_summary() -> None:
    samples = [
        {"setup_latency_ms": 5.0, "telemetry": {"fallback_count": 0}},   # warmup
        {"setup_latency_ms": 10.0, "telemetry": {"fallback_count": 0}},
        {"setup_latency_ms": 20.0, "telemetry": {"fallback_count": 1}},
    ]
    idx = {"i": 0}

    def probe():
        value = samples[idx["i"]]
        idx["i"] += 1
        return value

    result = RuntimeBenchmarkService.run_benchmark(probe=probe, repeats=2, warmup_runs=1)
    assert result["metadata"]["warmup_runs"] == 1
    assert result["summary"]["latency_ms"]["count"] == 2
    assert result["summary"]["latency_ms"]["mean"] == 15.0
    assert result["summary"]["fallback"]["fallback_runs"] == 1
    assert idx["i"] == 3


def test_run_benchmark_rejects_negative_warmup_runs() -> None:
    def probe():
        return {}

    try:
        RuntimeBenchmarkService.run_benchmark(probe=probe, repeats=1, warmup_runs=-1)
        assert False, "Expected ValueError for warmup_runs=-1"
    except ValueError as exc:
        assert "warmup_runs must be" in str(exc)


def test_run_benchmark_includes_custom_profile() -> None:
    def probe():
        return {"setup_latency_ms": 10.0, "telemetry": {"fallback_count": 0}}

    result = RuntimeBenchmarkService.run_benchmark(
        probe=probe,
        repeats=1,
        profile="ci-linux-gpu",
    )
    assert result["metadata"]["profile"] == "ci-linux-gpu"

