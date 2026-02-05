"""
CLI smoke tests.

These tests do not require a real database. We patch out database access and
pipeline execution to validate Click wiring, exit codes, and output behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from click.testing import CliRunner

from entity_resolution import cli as cli_module


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


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

    def fake_get_database(**kwargs: Any) -> object:
        captured["db_kwargs"] = kwargs
        return object()

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            captured["pipeline_db"] = db
            captured["pipeline_config_path"] = config_path

        def run(self) -> Dict[str, Any]:
            return {"ok": True, "blocking": {"candidate_pairs": 0}}

    monkeypatch.setattr(cli_module, "get_database", fake_get_database)
    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 0
    assert "Pipeline execution successful!" in result.output
    # Output includes a pretty-printed multi-line JSON block.
    lines = [line for line in result.output.splitlines() if line.strip()]
    start_idx = next(i for i, line in enumerate(lines) if line.lstrip().startswith("{"))
    json_text = "\n".join(lines[start_idx:])
    assert json.loads(json_text)["ok"] is True


def test_cli_run_db_connection_failure_exit_1(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    def fake_get_database(**kwargs: Any) -> object:
        raise RuntimeError("db down")

    monkeypatch.setattr(cli_module, "get_database", fake_get_database)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 1
    assert "Error: db down" in result.output


def test_cli_run_pipeline_init_failure_exit_1(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    def fake_get_database(**kwargs: Any) -> object:
        return object()

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            raise ValueError("bad config")

    monkeypatch.setattr(cli_module, "get_database", fake_get_database)
    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 1
    assert "Error: bad config" in result.output


def test_cli_run_pipeline_execution_failure_exit_1(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    def fake_get_database(**kwargs: Any) -> object:
        return object()

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def run(self) -> Dict[str, Any]:
            raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "get_database", fake_get_database)
    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(cli_module.main, ["run", "-c", str(config_path)])
    assert result.exit_code == 1
    assert "Error: boom" in result.output


def test_cli_run_passes_cli_overrides_to_get_database(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("entity_resolution: {}\n")

    captured: Dict[str, Any] = {}

    def fake_get_database(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    class FakePipeline:
        def __init__(self, db: object, config_path: str):
            pass

        def run(self) -> Dict[str, Any]:
            return {"ok": True}

    monkeypatch.setattr(cli_module, "get_database", fake_get_database)
    monkeypatch.setattr(cli_module, "ConfigurableERPipeline", FakePipeline)

    result = runner.invoke(
        cli_module.main,
        [
            "run",
            "-c",
            str(config_path),
            "-d",
            "mydb",
            "--host",
            "example",
            "--port",
            "1234",
            "-u",
            "alice",
            "-p",
            "secret",
        ],
    )
    assert result.exit_code == 0
    assert captured["database"] == "mydb"
    assert captured["host"] == "example"
    assert captured["port"] == 1234
    assert captured["username"] == "alice"
    assert captured["password"] == "secret"


def test_cli_run_config_file_not_found(runner: CliRunner) -> None:
    result = runner.invoke(cli_module.main, ["run", "-c", "no_such_file.yaml"])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower()

