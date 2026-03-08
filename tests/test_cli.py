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

