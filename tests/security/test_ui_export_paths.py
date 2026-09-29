"""The export routes must only write to, and serve from, their own directory.

Attacker: anyone who can call the Workbench API. That is anyone who can reach
the port when no auth token is configured, and any token holder when one is.

* POST /api/export/{collection} took ``output_dir`` and ``filename_prefix`` from
  the request body, so a caller could write export files anywhere the server
  process could, including through ``"../"`` in the prefix.
* GET .../download/{filename} served any file in the system temp directory
  whose name used "safe" characters, not only exports. Meanwhile it never found
  real exports, which went to a fresh mkdtemp subdirectory it did not search.

These tests use the real ClusterExportService, so the round trip is the one a
browser performs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from entity_resolution.ui.app import create_app  # noqa: E402


class _EmptyDB:
    """A database with no clusters. Not a MagicMock: unknown calls raise."""

    name = "export_test_db"

    class _AQL:
        def execute(self, query, bind_vars=None, **kwargs):
            return iter([])

    aql = _AQL()

    def has_collection(self, name):
        return False


@pytest.fixture
def client():
    return TestClient(create_app(db=_EmptyDB()))


def test_client_cannot_choose_the_output_directory(client, tmp_path: Path) -> None:
    target = tmp_path / "chosen_by_client"
    resp = client.post("/api/export/companies", json={"output_dir": str(target)})
    assert resp.status_code == 422
    assert not target.exists()


@pytest.mark.parametrize("prefix", ["../../escaped", "a/b", "..", "x" * 65, ""])
def test_prefix_cannot_carry_a_path(client, prefix: str) -> None:
    resp = client.post("/api/export/companies", json={"filename_prefix": prefix})
    assert resp.status_code == 422


def test_export_then_download_round_trip(client) -> None:
    resp = client.post("/api/export/companies", json={"filename_prefix": "weekly"})
    assert resp.status_code == 200, resp.text
    files = resp.json()["output_files"]
    assert "/" not in files["json"] and files["json"].startswith("weekly_")
    for name in files.values():
        download = client.get(f"/api/export/companies/download/{name}")
        assert download.status_code == 200, name


def test_download_does_not_serve_other_temp_files(client) -> None:
    with tempfile.NamedTemporaryFile(
        dir=tempfile.gettempdir(), prefix="not_an_export_", suffix=".json", delete=False
    ) as handle:
        handle.write(b'{"secret": true}')
        name = Path(handle.name).name
    try:
        # Previously served straight out of the system temp directory.
        assert client.get(f"/api/export/companies/download/{name}").status_code == 404
    finally:
        Path(handle.name).unlink()


@pytest.mark.parametrize("name", ["..%2F..%2Fetc%2Fpasswd", "config.yaml", ".env"])
def test_download_rejects_names_that_are_not_exports(client, name: str) -> None:
    assert client.get(f"/api/export/companies/download/{name}").status_code in (400, 404)


def test_unknown_api_path_is_a_404_when_the_spa_is_served(tmp_path: Path, monkeypatch) -> None:
    # With a built frontend present, the SPA fallback answered every unmatched
    # path, API paths included, with index.html and a 200.
    import entity_resolution.ui.app as app_module

    (tmp_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()  # a real build always has one
    monkeypatch.setattr(app_module, "_STATIC_DIR", tmp_path)
    client = TestClient(app_module.create_app(db=_EmptyDB()))
    assert client.get("/some/page").status_code == 200  # the SPA still serves its routes
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
