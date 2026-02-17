import logging
import subprocess

import pytest

from entity_resolution.services.address_er_service import AddressERService


class _DummyCollection:
    def truncate(self) -> None:
        return None


class _DummyDB:
    name = "entity_resolution_test"

    def has_collection(self, name: str) -> bool:
        return True

    def create_collection(self, name: str, edge: bool = False):
        return _DummyCollection()

    def collection(self, name: str):
        return _DummyCollection()


def test_arangoimport_failure_does_not_log_password(monkeypatch: pytest.MonkeyPatch, caplog, tmp_path) -> None:
    secret = "supersecret-password"
    monkeypatch.setenv("ARANGO_HOST", "localhost")
    monkeypatch.setenv("ARANGO_PORT", "18530")
    monkeypatch.setenv("ARANGO_USERNAME", "root")
    monkeypatch.setenv("ARANGO_PASSWORD", secret)

    service = AddressERService(db=_DummyDB(), config={"edge_loading_method": "csv"})

    # Avoid fallback path doing real work.
    monkeypatch.setattr(service, "_create_edges", lambda _blocks: 0)

    def _fake_run(_cmd, capture_output, text, check, timeout):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=_cmd,
            output=f"created: 0 (password={secret})",
            stderr=f"ERROR: auth failed for password {secret}",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    caplog.set_level(logging.DEBUG)
    blocks = {"block1": ["addresses/a", "addresses/b"]}
    csv_path = tmp_path / "edges.csv"

    service._create_edges_via_csv(blocks, csv_path=str(csv_path))

    assert secret not in caplog.text

