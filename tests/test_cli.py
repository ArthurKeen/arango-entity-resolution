"""
CLI smoke tests.

These tests do not require a real database. We patch out database access and
pipeline execution to validate Click wiring, exit codes, and output behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from click.testing import CliRunner

from entity_resolution import cli as cli_module


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _extract_json_block(output: str) -> Any:
    lines = [line for line in output.splitlines() if line.strip()]
    start_idx = next(i for i, line in enumerate(lines) if line.lstrip().startswith("{") or line.lstrip().startswith("["))
    return json.loads("\n".join(lines[start_idx:]))


def test_cli_help(runner: CliRunner) -> None:
    result = runner.invoke(cli_module.main, ["--help"])
    assert result.exit_code == 0
    assert "ArangoDB Entity Resolution CLI" in result.output


def test_cli_version(runner: CliRunner) -> None:
    result = runner.invoke(cli_module.main, ["--version"])
    assert result.exit_code == 0
    # Click prints "<prog>, version X"
    assert "version" in result.output.lower()


def test_cli_run_success_outputs_json(runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    captured: Dict[str, Any] = {}

    def fake_get_db_from_options(*args: Any) -> object:
        captured["db_args"] = args
        return object()

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            captured["pipeline_db"] = db
            captured["pipeline_config_path"] = config_path

        def run(self) -> Dict[str, Any]:
            return {"ok": True, "blocking": {"candidate_pairs": 0}}

    monkeypatch.setattr(cli_module, "_get_db_from_options", fake_get_db_from_options)
    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 0
    assert "Pipeline execution successful!" in result.output
    assert _extract_json_block(result.output)["ok"] is True


def test_cli_run_db_connection_failure_exit_1(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    def fake_get_db_from_options(*args: Any) -> object:
        raise RuntimeError("db down")

    monkeypatch.setattr(cli_module, "_get_db_from_options", fake_get_db_from_options)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 1
    assert "Error: db down" in result.output


def test_cli_run_pipeline_init_failure_exit_1(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    def fake_get_db_from_options(*args: Any) -> object:
        return object()

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            raise ValueError("bad config")

    monkeypatch.setattr(cli_module, "_get_db_from_options", fake_get_db_from_options)
    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 1
    assert "Error: bad config" in result.output


def test_cli_run_pipeline_execution_failure_exit_1(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    def fake_get_db_from_options(*args: Any) -> object:
        return object()

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def run(self) -> Dict[str, Any]:
            raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "_get_db_from_options", fake_get_db_from_options)
    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 1
    assert "Error: boom" in result.output


def test_resolve_connection_args_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "get_connection_args",
        lambda: {
            "host": "localhost",
            "port": 8529,
            "username": "root",
            "password": "pw",
            "database": "default_db",
        },
    )

    resolved = cli_module._resolve_connection_args("mydb", "example", 1234, "alice", "secret")

    assert resolved == {
        "host": "example",
        "port": 1234,
        "username": "alice",
        "password": "secret",
        "database": "mydb",
    }


def test_get_db_from_options_uses_direct_client_for_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "get_connection_args",
        lambda: {
            "host": "localhost",
            "port": 8529,
            "username": "root",
            "password": "pw",
            "database": "default_db",
        },
    )

    captured: Dict[str, Any] = {}

    class FakeDB:
        def properties(self) -> Dict[str, Any]:
            captured["properties_called"] = True
            return {}

    class FakeClient:
        def __init__(self, hosts: str):
            captured["hosts"] = hosts

        def db(self, database: str, username: str, password: str) -> FakeDB:
            captured["database"] = database
            captured["username"] = username
            captured["password"] = password
            return FakeDB()

    monkeypatch.setattr(cli_module, "ArangoClient", FakeClient)

    db = cli_module._get_db_from_options("mydb", "example", 1234, "alice", "secret")
    assert isinstance(db, FakeDB)
    assert captured["hosts"] == "http://example:1234"
    assert captured["database"] == "mydb"
    assert captured["username"] == "alice"
    assert captured["password"] == "secret"
    assert captured["properties_called"] is True


def test_cli_run_config_file_not_found(runner: CliRunner) -> None:
    result = runner.invoke(cli_module.main, ["run", "-c", "no_such_file.yaml"])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower()


def test_cli_status_outputs_json(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "run_pipeline_status",
        lambda **kwargs: {"collection": kwargs["collection"], "total_documents": 42},
    )
    monkeypatch.setattr(
        cli_module,
        "_resolve_connection_args",
        lambda *args: {
            "host": "localhost",
            "port": 8529,
            "username": "root",
            "password": "pw",
            "database": "db",
        },
    )

    result = runner.invoke(cli_module.main, ["status", "--collection", "companies"])
    assert result.exit_code == 0
    assert _extract_json_block(result.output)["total_documents"] == 42


def test_cli_status_include_runtime_health_requires_config(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "run_pipeline_status",
        lambda **kwargs: {"collection": kwargs["collection"], "total_documents": 42},
    )
    monkeypatch.setattr(
        cli_module,
        "_resolve_connection_args",
        lambda *args: {
            "host": "localhost",
            "port": 8529,
            "username": "root",
            "password": "pw",
            "database": "db",
        },
    )

    result = runner.invoke(
        cli_module.main,
        ["status", "--collection", "companies", "--include-runtime-health"],
    )
    assert result.exit_code == 1
    assert "--include-runtime-health requires --config" in result.output


def test_cli_status_include_runtime_health_with_config(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")

    monkeypatch.setattr(
        cli_module,
        "run_pipeline_status",
        lambda **kwargs: {"collection": kwargs["collection"], "total_documents": 42},
    )
    monkeypatch.setattr(
        cli_module,
        "_resolve_connection_args",
        lambda *args: {
            "host": "localhost",
            "port": 8529,
            "username": "root",
            "password": "pw",
            "database": "db",
        },
    )
    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            self.db = db
            self.config_path = config_path

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"enabled": True, "runtime": "pytorch", "startup_mode": startup_mode}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(
        cli_module.main,
        [
            "status",
            "--collection",
            "companies",
            "--include-runtime-health",
            "--config",
            str(cfg),
            "--startup-mode",
            "strict",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["total_documents"] == 42
    assert payload["runtime_health"]["enabled"] is True
    assert payload["runtime_health"]["startup_mode"] == "strict"


def test_cli_runtime_health_export_writes_artifact(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    out_dir = tmp_path / "artifacts"

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            self.db = db
            self.config_path = config_path

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"enabled": True, "runtime": "pytorch", "startup_mode": startup_mode}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    def fake_export_snapshot(snapshot, output_dir, filename_prefix):
        assert snapshot["enabled"] is True
        assert filename_prefix == "rt_health"
        assert output_dir == str(out_dir)
        return str(out_dir / "rt_health_20260314_000000.json")

    monkeypatch.setattr(
        cli_module.RuntimeTelemetryService,
        "export_snapshot",
        staticmethod(fake_export_snapshot),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-export",
            "-c",
            str(cfg),
            "--output-dir",
            str(out_dir),
            "--filename-prefix",
            "rt_health",
            "--startup-mode",
            "strict",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["output_file"].endswith("rt_health_20260314_000000.json")
    assert payload["snapshot"]["startup_mode"] == "strict"


def test_cli_runtime_health_baseline_and_compare(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            self.db = db
            self.config_path = config_path

        def get_embedding_runtime_health(self, startup_mode=None):
            return {
                "enabled": True,
                "runtime": "pytorch",
                "model_name": "all-MiniLM-L6-v2",
                "resolved_provider": "pytorch",
                "resolved_device": "cpu",
                "setup_latency_ms": 10.0,
                "telemetry": {"fallback_count": 0},
                "startup_mode": startup_mode,
            }

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    baseline_result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-baseline",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--label",
            "dev-mac",
        ],
    )
    assert baseline_result.exit_code == 0
    baseline_payload = _extract_json_block(baseline_result.output)
    assert baseline_payload["registry_file"] == str(registry)
    assert baseline_payload["baseline"]["label"] == "dev-mac"

    compare_result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-compare",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--label",
            "dev-mac",
        ],
    )
    assert compare_result.exit_code == 0
    compare_payload = _extract_json_block(compare_result.output)
    assert compare_payload["baseline_found"] is True
    assert compare_payload["regressions"]["latency_regression"] is False


def test_cli_runtime_health_benchmark_outputs_summary(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"setup_latency_ms": 12.0, "telemetry": {"fallback_count": 0}}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    monkeypatch.setattr(
        cli_module.RuntimeBenchmarkService,
        "run_benchmark",
        staticmethod(
            lambda probe, repeats: {
                "metadata": {"repeats": repeats},
                "summary": {"latency_ms": {"mean": 12.0}},
                "runs": [],
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-benchmark",
            "-c",
            str(cfg),
            "--repeats",
            "3",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["metadata"]["repeats"] == 3
    assert payload["summary"]["latency_ms"]["mean"] == 12.0


def test_cli_runtime_health_benchmark_writes_artifact(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    out_dir = tmp_path / "bench"

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"setup_latency_ms": 12.0, "telemetry": {"fallback_count": 0}}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    monkeypatch.setattr(
        cli_module.RuntimeBenchmarkService,
        "run_benchmark",
        staticmethod(lambda probe, repeats: {"metadata": {}, "summary": {}, "runs": []}),
    )
    monkeypatch.setattr(
        cli_module.RuntimeBenchmarkService,
        "export_benchmark",
        staticmethod(
            lambda benchmark_result, output_dir, filename_prefix: str(
                Path(output_dir) / f"{filename_prefix}_20260314_000000.json"
            )
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-benchmark",
            "-c",
            str(cfg),
            "--output-dir",
            str(out_dir),
            "--filename-prefix",
            "bench",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["output_file"].endswith("bench_20260314_000000.json")


def test_cli_runtime_health_compare_writes_report_artifacts(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"
    registry.write_text('{"version":1,"baselines":[]}')
    out_dir = tmp_path / "reports"

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            self.db = db
            self.config_path = config_path

        def get_embedding_runtime_health(self, startup_mode=None):
            return {
                "enabled": True,
                "runtime": "pytorch",
                "model_name": "all-MiniLM-L6-v2",
                "resolved_provider": "pytorch",
                "resolved_device": "cpu",
                "setup_latency_ms": 10.0,
                "telemetry": {"fallback_count": 0},
            }

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "compare_snapshot",
        staticmethod(
            lambda **kwargs: {
                "baseline_found": True,
                "key": "k",
                "comparison": {},
                "regressions": {},
            }
        ),
    )
    monkeypatch.setattr(
        cli_module.RuntimeCompareReportService,
        "export_report",
        staticmethod(
            lambda comparison, output_dir, filename_prefix: {
                "json": str(Path(output_dir) / f"{filename_prefix}.json"),
                "markdown": str(Path(output_dir) / f"{filename_prefix}.md"),
                "csv": str(Path(output_dir) / f"{filename_prefix}.csv"),
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-compare",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--output-dir",
            str(out_dir),
            "--filename-prefix",
            "cmp",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["output_files"]["json"].endswith("cmp.json")


def test_cli_runtime_health_gate_success(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"
    registry.write_text('{"version":1,"baselines":[]}')

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"enabled": True, "runtime": "pytorch"}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "compare_snapshot",
        staticmethod(
            lambda **kwargs: {
                "baseline_found": True,
                "key": "k",
                "comparison": {},
                "regressions": {
                    "latency_regression": False,
                    "fallback_regression": False,
                },
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-gate",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["baseline_found"] is True


def test_cli_runtime_health_gate_fail_on_regression_exits_2(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"
    registry.write_text('{"version":1,"baselines":[]}')

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"enabled": True, "runtime": "pytorch"}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "compare_snapshot",
        staticmethod(
            lambda **kwargs: {
                "baseline_found": True,
                "key": "k",
                "comparison": {},
                "regressions": {
                    "latency_regression": True,
                    "fallback_regression": False,
                },
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-gate",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--fail-on-regression",
        ],
    )
    assert result.exit_code == 2


def test_cli_runtime_health_gate_bootstraps_missing_baseline(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"
    registry.write_text('{"version":1,"baselines":[]}')

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {
                "enabled": True,
                "runtime": "pytorch",
                "model_name": "all-MiniLM-L6-v2",
                "resolved_provider": "pytorch",
                "resolved_device": "cpu",
            }

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "compare_snapshot",
        staticmethod(
            lambda **kwargs: {
                "baseline_found": False,
                "key": "missing-key",
                "snapshot": kwargs["snapshot"],
            }
        ),
    )
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "upsert_baseline",
        staticmethod(
            lambda **kwargs: {
                "key": "missing-key",
                "label": kwargs.get("label"),
                "snapshot": kwargs["snapshot"],
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-gate",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--bootstrap-baseline",
            "--label",
            "dev-mac",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["baseline_found"] is False
    assert payload["baseline_bootstrapped"] is True
    assert payload["baseline_entry"]["label"] == "dev-mac"


def test_cli_runtime_quality_compare_and_fail_on_regression(
    runner: CliRunner, tmp_path: Path
) -> None:
    baseline = tmp_path / "baseline_quality.json"
    current = tmp_path / "current_quality.json"
    baseline.write_text('{"cosine_drift":0.003,"topk_overlap":0.99}')
    current.write_text('{"cosine_drift":0.02,"topk_overlap":0.90}')

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-quality-compare",
            "--current-metrics",
            str(current),
            "--baseline-metrics",
            str(baseline),
            "--fail-on-regression",
        ],
    )
    assert result.exit_code == 2
    payload = _extract_json_block(result.output)
    assert payload["regressions"]["quality_regression"] is True


def test_cli_runtime_quality_corpus_init(
    runner: CliRunner, tmp_path: Path
) -> None:
    corpus_path = tmp_path / "corpus.json"
    result = runner.invoke(
        cli_module.main,
        [
            "runtime-quality-corpus-init",
            "--output",
            str(corpus_path),
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["corpus_file"] == str(corpus_path)
    assert corpus_path.exists()


def test_cli_runtime_quality_benchmark_outputs_metrics(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}")

    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "load_corpus",
        staticmethod(lambda path: {"metadata": {"name": "tiny"}}),
    )
    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "run_benchmark",
        staticmethod(
            lambda corpus, embed_texts: {
                "metadata": {"corpus_name": "tiny"},
                "cosine_drift": 0.005,
                "topk_overlap": 0.97,
            }
        ),
    )

    class FakeEmbeddingService:
        def __init__(self, model_name, device, batch_size):
            self.device = "cpu"

        def generate_embeddings_batch(self, records, text_fields, batch_size, show_progress):
            return _FakeArray([[1.0, 0.0] for _ in records])

    class _FakeArray:
        def __init__(self, rows):
            self._rows = rows

        def tolist(self):
            return self._rows

    monkeypatch.setattr(cli_module, "EmbeddingService", FakeEmbeddingService)

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-quality-benchmark",
            "--corpus",
            str(corpus),
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["cosine_drift"] == 0.005
    assert payload["topk_overlap"] == 0.97
    assert payload["metadata"]["resolved_device"] == "cpu"


def test_cli_runtime_quality_benchmark_writes_metrics_artifact(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}")
    out_dir = tmp_path / "quality"

    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "load_corpus",
        staticmethod(lambda path: {"metadata": {"name": "tiny"}}),
    )
    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "run_benchmark",
        staticmethod(
            lambda corpus, embed_texts: {
                "metadata": {"corpus_name": "tiny"},
                "cosine_drift": 0.004,
                "topk_overlap": 0.98,
            }
        ),
    )
    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "export_metrics",
        staticmethod(
            lambda metrics, output_dir, filename_prefix: str(
                Path(output_dir) / f"{filename_prefix}_20260316_000000.json"
            )
        ),
    )

    class FakeEmbeddingService:
        def __init__(self, model_name, device, batch_size):
            self.device = "cpu"

        def generate_embeddings_batch(self, records, text_fields, batch_size, show_progress):
            return _FakeArray([[1.0, 0.0] for _ in records])

    class _FakeArray:
        def __init__(self, rows):
            self._rows = rows

        def tolist(self):
            return self._rows

    monkeypatch.setattr(cli_module, "EmbeddingService", FakeEmbeddingService)

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-quality-benchmark",
            "--corpus",
            str(corpus),
            "--output-dir",
            str(out_dir),
            "--filename-prefix",
            "quality_metrics",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["output_file"].endswith("quality_metrics_20260316_000000.json")


def test_cli_runtime_quality_baseline_writes_stable_file(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}")
    out_dir = tmp_path / "quality"

    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "load_corpus",
        staticmethod(lambda path: {"metadata": {"name": "tiny"}}),
    )
    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "run_benchmark",
        staticmethod(
            lambda corpus, embed_texts: {
                "metadata": {"corpus_name": "tiny"},
                "cosine_drift": 0.004,
                "topk_overlap": 0.98,
            }
        ),
    )
    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "write_metrics_file",
        staticmethod(lambda metrics, output_path, overwrite: output_path),
    )

    class FakeEmbeddingService:
        def __init__(self, model_name, device, batch_size):
            self.device = "cpu"

        def generate_embeddings_batch(self, records, text_fields, batch_size, show_progress):
            return _FakeArray([[1.0, 0.0] for _ in records])

    class _FakeArray:
        def __init__(self, rows):
            self._rows = rows

        def tolist(self):
            return self._rows

    monkeypatch.setattr(cli_module, "EmbeddingService", FakeEmbeddingService)

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-quality-baseline",
            "--corpus",
            str(corpus),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["output_file"].endswith("baseline_metrics.json")
    assert payload["metrics"]["metadata"]["resolved_device"] == "cpu"


def test_cli_runtime_quality_baseline_passes_no_overwrite_flag(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}")
    out_dir = tmp_path / "quality"
    captured = {}

    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "load_corpus",
        staticmethod(lambda path: {"metadata": {"name": "tiny"}}),
    )
    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "run_benchmark",
        staticmethod(
            lambda corpus, embed_texts: {
                "metadata": {"corpus_name": "tiny"},
                "cosine_drift": 0.004,
                "topk_overlap": 0.98,
            }
        ),
    )

    def _fake_write_metrics_file(metrics, output_path, overwrite):
        captured["overwrite"] = overwrite
        return output_path

    monkeypatch.setattr(
        cli_module.RuntimeQualityBenchmarkService,
        "write_metrics_file",
        staticmethod(_fake_write_metrics_file),
    )

    class FakeEmbeddingService:
        def __init__(self, model_name, device, batch_size):
            self.device = "cpu"

        def generate_embeddings_batch(self, records, text_fields, batch_size, show_progress):
            return _FakeArray([[1.0, 0.0] for _ in records])

    class _FakeArray:
        def __init__(self, rows):
            self._rows = rows

        def tolist(self):
            return self._rows

    monkeypatch.setattr(cli_module, "EmbeddingService", FakeEmbeddingService)

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-quality-baseline",
            "--corpus",
            str(corpus),
            "--output-dir",
            str(out_dir),
            "--no-overwrite",
        ],
    )
    assert result.exit_code == 0
    assert captured["overwrite"] is False


def test_cli_runtime_health_gate_includes_quality_gate(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"
    registry.write_text('{"version":1,"baselines":[]}')
    baseline = tmp_path / "baseline_quality.json"
    current = tmp_path / "current_quality.json"
    baseline.write_text('{"cosine_drift":0.003,"topk_overlap":0.99}')
    current.write_text('{"cosine_drift":0.008,"topk_overlap":0.97}')

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"enabled": True, "runtime": "pytorch"}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "compare_snapshot",
        staticmethod(
            lambda **kwargs: {
                "baseline_found": True,
                "key": "k",
                "comparison": {},
                "regressions": {
                    "latency_regression": False,
                    "fallback_regression": False,
                },
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-gate",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--quality-current-metrics",
            str(current),
            "--quality-baseline-metrics",
            str(baseline),
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["quality_gate"]["regressions"]["quality_regression"] is False


def test_cli_runtime_health_gate_includes_quality_gate_from_corpus(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"
    registry.write_text('{"version":1,"baselines":[]}')
    baseline = tmp_path / "baseline_quality.json"
    corpus = tmp_path / "quality_corpus.json"
    baseline.write_text('{"cosine_drift":0.003,"topk_overlap":0.99}')
    corpus.write_text("{}")

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"enabled": True, "runtime": "pytorch"}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "compare_snapshot",
        staticmethod(
            lambda **kwargs: {
                "baseline_found": True,
                "key": "k",
                "comparison": {},
                "regressions": {
                    "latency_regression": False,
                    "fallback_regression": False,
                },
            }
        ),
    )
    monkeypatch.setattr(
        cli_module,
        "_build_runtime_quality_metrics",
        lambda **kwargs: {"cosine_drift": 0.008, "topk_overlap": 0.97},
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-gate",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--quality-corpus",
            str(corpus),
            "--quality-baseline-metrics",
            str(baseline),
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["quality_gate"]["current_source"] == "corpus_benchmark"
    assert payload["quality_gate"]["regressions"]["quality_regression"] is False


def test_cli_runtime_health_gate_quality_corpus_requires_baseline(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("entity_resolution: {}\n")
    registry = tmp_path / "runtime_registry.json"
    registry.write_text('{"version":1,"baselines":[]}')
    corpus = tmp_path / "quality_corpus.json"
    corpus.write_text("{}")

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def get_embedding_runtime_health(self, startup_mode=None):
            return {"enabled": True, "runtime": "pytorch"}

    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)
    monkeypatch.setattr(
        cli_module.RuntimeProfileRegistry,
        "compare_snapshot",
        staticmethod(
            lambda **kwargs: {
                "baseline_found": True,
                "key": "k",
                "comparison": {},
                "regressions": {
                    "latency_regression": False,
                    "fallback_regression": False,
                },
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-health-gate",
            "-c",
            str(cfg),
            "--registry-file",
            str(registry),
            "--quality-corpus",
            str(corpus),
        ],
    )
    assert result.exit_code == 1
    assert "Quality gate requires --quality-baseline-metrics" in result.output


def test_cli_runtime_quality_compare_writes_report_artifacts(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    baseline = tmp_path / "baseline_quality.json"
    current = tmp_path / "current_quality.json"
    baseline.write_text('{"cosine_drift":0.003,"topk_overlap":0.99}')
    current.write_text('{"cosine_drift":0.008,"topk_overlap":0.97}')
    out_dir = tmp_path / "quality_reports"

    monkeypatch.setattr(
        cli_module.RuntimeCompareReportService,
        "export_report",
        staticmethod(
            lambda comparison, output_dir, filename_prefix: {
                "json": str(Path(output_dir) / f"{filename_prefix}.json"),
                "markdown": str(Path(output_dir) / f"{filename_prefix}.md"),
                "csv": str(Path(output_dir) / f"{filename_prefix}.csv"),
            }
        ),
    )

    result = runner.invoke(
        cli_module.main,
        [
            "runtime-quality-compare",
            "--current-metrics",
            str(current),
            "--baseline-metrics",
            str(baseline),
            "--output-dir",
            str(out_dir),
            "--filename-prefix",
            "quality_cmp",
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["output_files"]["json"].endswith("quality_cmp.json")


def test_cli_clusters_outputs_json(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "run_get_clusters",
        lambda **kwargs: [{"cluster_id": "c1", "size": 2}],
    )
    monkeypatch.setattr(
        cli_module,
        "_resolve_connection_args",
        lambda *args: {
            "host": "localhost",
            "port": 8529,
            "username": "root",
            "password": "pw",
            "database": "db",
        },
    )

    result = runner.invoke(cli_module.main, ["clusters", "--collection", "companies"])
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload[0]["cluster_id"] == "c1"


def test_cli_export_outputs_paths(runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())

    class FakeExportService:
        cluster_collection = "companies_clusters"

        def __init__(self, **kwargs: Any):
            pass

        def export(self, output_dir: str, filename_prefix: str, limit: Any) -> Dict[str, Any]:
            return {
                "json": str(tmp_path / "out.json"),
                "csv": str(tmp_path / "out.csv"),
                "clusters_exported": 3,
            }

    monkeypatch.setattr(cli_module, "ClusterExportService", FakeExportService)

    result = runner.invoke(
        cli_module.main,
        ["export", "--collection", "companies", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["clusters_exported"] == 3
    assert payload["output_files"]["json"].endswith("out.json")


def test_cli_benchmark_outputs_results(runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ground_truth = tmp_path / "ground_truth.json"
    ground_truth.write_text("[]")

    monkeypatch.setattr(cli_module, "_get_db_from_options", lambda *args: object())
    monkeypatch.setattr(
        cli_module,
        "run_blocking_benchmark",
        lambda **kwargs: {
            "metadata": {"collection": kwargs["collection_name"]},
            "baseline": {"precision": 0.8},
            "hybrid": {"precision": 0.9},
            "improvements": {"precision_delta": 0.1},
            "output_files": {"json": "a.json", "csv": "a.csv"},
        },
    )

    result = runner.invoke(
        cli_module.main,
        [
            "benchmark",
            "--collection",
            "companies",
            "--ground-truth",
            str(ground_truth),
            "--baseline-field",
            "name",
            "--search-view",
            "companies_search",
            "--search-field",
            "name",
            "--output-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    payload = _extract_json_block(result.output)
    assert payload["metadata"]["collection"] == "companies"
    assert payload["output_files"]["json"] == "a.json"

