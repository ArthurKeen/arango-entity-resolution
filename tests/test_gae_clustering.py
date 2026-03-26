"""Tests for GAE clustering config, backend, and auto-selection integration."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from entity_resolution.config.er_config import (
    ClusteringConfig,
    GAEClusteringConfig,
)
from entity_resolution.services.clustering_backends.gae_wcc import GAEWCCBackend
from entity_resolution.services.wcc_clustering_service import WCCClusteringService


# ── GAEClusteringConfig ──────────────────────────────────────────────

class TestGAEClusteringConfig:

    def test_defaults(self):
        cfg = GAEClusteringConfig()
        assert cfg.enabled is False
        assert cfg.deployment_mode == "self_managed"
        assert cfg.graph_name is None
        assert cfg.engine_size == "e16"
        assert cfg.auto_cleanup is True
        assert cfg.timeout_seconds == 3600

    def test_from_dict(self):
        cfg = GAEClusteringConfig.from_dict({
            "enabled": True,
            "deployment_mode": "auto",
            "graph_name": "my_graph",
            "engine_size": "e32",
            "timeout_seconds": 600,
        })
        assert cfg.enabled is True
        assert cfg.deployment_mode == "auto"
        assert cfg.graph_name == "my_graph"
        assert cfg.engine_size == "e32"
        assert cfg.timeout_seconds == 600

    def test_to_dict(self):
        cfg = GAEClusteringConfig(enabled=True, graph_name="g1")
        d = cfg.to_dict()
        assert d["enabled"] is True
        assert d["graph_name"] == "g1"
        assert "deployment_mode" in d

    def test_to_dict_omits_none_graph_name(self):
        cfg = GAEClusteringConfig()
        d = cfg.to_dict()
        assert "graph_name" not in d

    def test_validate_valid(self):
        cfg = GAEClusteringConfig(
            enabled=True, deployment_mode="self_managed", graph_name="g1"
        )
        assert cfg.validate() == []

    def test_validate_auto_mode_no_graph_name(self):
        cfg = GAEClusteringConfig(enabled=True, deployment_mode="auto")
        assert cfg.validate() == []

    def test_validate_self_managed_requires_graph_name(self):
        cfg = GAEClusteringConfig(enabled=True, deployment_mode="self_managed")
        errors = cfg.validate()
        assert len(errors) == 1
        assert "graph_name" in errors[0]

    def test_validate_invalid_deployment_mode(self):
        cfg = GAEClusteringConfig(deployment_mode="cloud")
        errors = cfg.validate()
        assert any("deployment_mode" in e for e in errors)

    def test_validate_invalid_timeout(self):
        cfg = GAEClusteringConfig(timeout_seconds=0)
        errors = cfg.validate()
        assert any("timeout_seconds" in e for e in errors)


# ── ClusteringConfig GAE integration ─────────────────────────────────

class TestClusteringConfigGAE:

    def test_gae_field_default_none(self):
        cfg = ClusteringConfig()
        assert cfg.gae is None

    def test_gae_field_set(self):
        gae = GAEClusteringConfig(enabled=True, graph_name="g")
        cfg = ClusteringConfig(gae=gae)
        assert cfg.gae is gae

    def test_from_dict_with_gae(self):
        cfg = ClusteringConfig.from_dict({
            "backend": "auto",
            "gae": {
                "enabled": True,
                "deployment_mode": "auto",
                "engine_size": "e16",
            },
        })
        assert cfg.gae is not None
        assert cfg.gae.enabled is True
        assert cfg.gae.deployment_mode == "auto"

    def test_from_dict_without_gae(self):
        cfg = ClusteringConfig.from_dict({"backend": "python_dfs"})
        assert cfg.gae is None

    def test_to_dict_includes_gae(self):
        gae = GAEClusteringConfig(enabled=True, graph_name="g")
        cfg = ClusteringConfig(gae=gae)
        d = cfg.to_dict()
        assert "gae" in d
        assert d["gae"]["enabled"] is True

    def test_to_dict_excludes_gae_when_none(self):
        cfg = ClusteringConfig()
        d = cfg.to_dict()
        assert "gae" not in d

    def test_validate_propagates_gae_errors(self):
        gae = GAEClusteringConfig(enabled=True, deployment_mode="self_managed")
        cfg = ClusteringConfig(gae=gae)
        errors = cfg.validate()
        assert any("graph_name" in e for e in errors)

    def test_gae_wcc_is_valid_backend(self):
        cfg = ClusteringConfig(backend="gae_wcc")
        assert cfg.validate() == []

    def test_default_backend_is_auto(self):
        cfg = ClusteringConfig()
        assert cfg.backend == "auto"


# ── GAEWCCBackend ────────────────────────────────────────────────────

def _make_mock_db():
    db = MagicMock()
    db.collection.return_value = MagicMock()
    return db


def _mock_connection(available: bool = True):
    """Create a mock GAE connection."""
    conn = MagicMock()
    conn.deploy_engine.return_value = {"id": "svc-1"}
    if available:
        conn.wait_for_engine_ready.return_value = True
    else:
        conn.deploy_engine.side_effect = RuntimeError("no GAE")
    return conn


class TestGAEWCCBackend:

    def test_backend_name(self):
        db = _make_mock_db()
        backend = GAEWCCBackend(db, "edges")
        assert backend.backend_name() == "gae_wcc"

    def test_is_available_returns_true_when_connection_ok(self):
        db = _make_mock_db()
        backend = GAEWCCBackend(db, "edges")
        backend._connection = _mock_connection(available=True)
        assert backend.is_available() is True

    def test_is_available_returns_false_when_connection_fails(self):
        db = _make_mock_db()
        backend = GAEWCCBackend(db, "edges")
        backend._connection = _mock_connection(available=False)
        assert backend.is_available() is False

    def test_is_available_returns_false_on_exception(self):
        db = _make_mock_db()
        backend = GAEWCCBackend(db, "edges")
        conn = MagicMock()
        conn.deploy_engine.side_effect = ConnectionError("nope")
        backend._connection = conn
        assert backend.is_available() is False

    def test_default_gae_config_created_when_none(self):
        db = _make_mock_db()
        backend = GAEWCCBackend(db, "edges")
        assert backend.gae_config is not None
        assert backend.gae_config.enabled is False


# ── Auto-select with GAE ─────────────────────────────────────────────

class TestAutoSelectWithGAE:

    def _make_service(
        self,
        edge_count: int = 100,
        gae_available: bool = False,
        gae_enabled: bool = False,
        threshold: int = 50,
    ):
        db = MagicMock()
        edge_coll = MagicMock()
        edge_coll.count.return_value = edge_count
        db.collection.return_value = edge_coll

        gae_config = GAEClusteringConfig(
            enabled=gae_enabled,
            deployment_mode="auto",
        ) if gae_enabled else None

        svc = WCCClusteringService(
            db=db,
            backend="auto",
            auto_select_threshold_edges=threshold,
            gae_config=gae_config,
        )

        with patch(
            "entity_resolution.services.clustering_backends.gae_wcc.GAEWCCBackend.is_available",
            return_value=gae_available,
        ):
            return svc, svc._get_backend()

    def test_auto_selects_gae_when_available_and_above_threshold(self):
        _, backend = self._make_service(
            edge_count=200, gae_available=True, gae_enabled=True, threshold=100,
        )
        assert backend.backend_name() == "gae_wcc"

    def test_auto_falls_back_when_gae_enabled_but_unavailable(self):
        _, backend = self._make_service(
            edge_count=200, gae_available=False, gae_enabled=True, threshold=100,
        )
        assert backend.backend_name() in ("python_union_find", "python_sparse")

    def test_auto_skips_gae_when_below_threshold(self):
        _, backend = self._make_service(
            edge_count=10, gae_available=True, gae_enabled=True, threshold=100,
        )
        assert backend.backend_name() == "python_union_find"

    def test_auto_skips_gae_when_not_enabled(self):
        _, backend = self._make_service(
            edge_count=200, gae_available=True, gae_enabled=False, threshold=100,
        )
        assert backend.backend_name() in ("python_union_find", "python_sparse")

    def test_gae_wcc_backend_dispatch(self):
        """Explicit ``backend='gae_wcc'`` routes to GAEWCCBackend."""
        db = MagicMock()
        db.collection.return_value = MagicMock()
        gae_config = GAEClusteringConfig(enabled=True, deployment_mode="auto")

        svc = WCCClusteringService(
            db=db, backend="gae_wcc", gae_config=gae_config,
        )
        backend = svc._get_backend()
        assert backend.backend_name() == "gae_wcc"

    def test_gae_stats_recorded_after_cluster(self):
        """Statistics include gae_job_id when GAE backend completes."""
        db = MagicMock()
        db.collection.return_value = MagicMock()
        gae_config = GAEClusteringConfig(enabled=True, deployment_mode="auto")

        svc = WCCClusteringService(
            db=db, backend="gae_wcc", gae_config=gae_config,
        )

        mock_backend = MagicMock()
        mock_backend.backend_name.return_value = "gae_wcc"
        mock_backend.cluster.return_value = [["a", "b"], ["c", "d"]]
        mock_backend.gae_job_id = "job-123"
        mock_backend.gae_runtime_seconds = 5.0

        with patch.object(svc, "_get_backend", return_value=mock_backend):
            svc.cluster(store_results=False)

        stats = svc.get_statistics()
        assert stats["gae_job_id"] == "job-123"
        assert stats["gae_runtime_seconds"] == 5.0
