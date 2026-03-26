"""Integration tests for GAE WCC clustering backend.

These tests require a running ArangoDB Enterprise instance with GAE enabled.
They are automatically skipped when GAE is not available.

To run these tests:
    1. Set ARANGO_HOST / ARANGO_PASSWORD for your GAE-enabled cluster
    2. Run: pytest tests/test_gae_integration.py -v
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock

from entity_resolution.config.er_config import GAEClusteringConfig
from entity_resolution.services.clustering_backends.gae_wcc import GAEWCCBackend


requires_gae = pytest.mark.skipif(
    not os.environ.get("ARANGO_GAE_ENABLED"),
    reason="Set ARANGO_GAE_ENABLED=1 and point to a GAE cluster to run",
)


def _get_test_db():
    """Connect to the test ArangoDB instance."""
    from arango import ArangoClient

    host = os.environ.get("ARANGO_HOST", "http://localhost:8529")
    password = os.environ.get("ARANGO_PASSWORD", "")
    db_name = os.environ.get("ARANGO_DB", "_system")

    client = ArangoClient(hosts=host)
    return client.db(db_name, username="root", password=password)


@requires_gae
class TestGAEIntegration:
    """Live integration tests against a GAE-enabled ArangoDB cluster."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = _get_test_db()
        self.edge_collection = "_test_gae_edges"
        self.vertex_collection = "_test_gae_vertices"

        for name in (self.edge_collection, self.vertex_collection):
            if self.db.has_collection(name):
                self.db.collection(name).truncate()
            else:
                is_edge = name == self.edge_collection
                self.db.create_collection(name, edge=is_edge)

        yield

        for name in (self.edge_collection, self.vertex_collection):
            if self.db.has_collection(name):
                self.db.delete_collection(name)

    def _seed_triangle(self):
        """Insert a simple triangle graph: A-B, B-C, A-C."""
        verts = self.db.collection(self.vertex_collection)
        for key in ("A", "B", "C", "D", "E"):
            verts.insert({"_key": key})

        edges = self.db.collection(self.edge_collection)
        prefix = self.vertex_collection
        edges.insert({"_from": f"{prefix}/A", "_to": f"{prefix}/B", "score": 0.9})
        edges.insert({"_from": f"{prefix}/B", "_to": f"{prefix}/C", "score": 0.8})
        edges.insert({"_from": f"{prefix}/A", "_to": f"{prefix}/C", "score": 0.7})
        edges.insert({"_from": f"{prefix}/D", "_to": f"{prefix}/E", "score": 0.95})

    def test_is_available(self):
        backend = GAEWCCBackend(
            self.db, self.edge_collection, self.vertex_collection,
        )
        assert backend.is_available() is True

    def test_cluster_finds_components(self):
        self._seed_triangle()
        gae_config = GAEClusteringConfig(
            enabled=True,
            deployment_mode="auto",
            engine_size="e16",
        )
        backend = GAEWCCBackend(
            self.db, self.edge_collection, self.vertex_collection,
            gae_config=gae_config,
        )
        clusters = backend.cluster()
        assert len(clusters) == 2
        sizes = sorted(len(c) for c in clusters)
        assert sizes == [2, 3]

    def test_cluster_returns_correct_keys(self):
        self._seed_triangle()
        gae_config = GAEClusteringConfig(
            enabled=True, deployment_mode="auto",
        )
        backend = GAEWCCBackend(
            self.db, self.edge_collection, self.vertex_collection,
            gae_config=gae_config,
        )
        clusters = backend.cluster()
        all_keys = sorted(k for c in clusters for k in c)
        assert all_keys == ["A", "B", "C", "D", "E"]


class TestGAENotAvailableFallback:
    """Verify graceful behavior when GAE is not present (community edition)."""

    def test_is_available_returns_false(self):
        db = MagicMock()
        backend = GAEWCCBackend(db, "edges")
        conn = MagicMock()
        conn.deploy_engine.side_effect = RuntimeError("no GAE")
        backend._connection = conn
        assert backend.is_available() is False

    def test_cluster_raises_error_when_deploy_fails(self):
        db = MagicMock()
        backend = GAEWCCBackend(db, "edges")
        conn = MagicMock()
        conn.deploy_engine.side_effect = RuntimeError("no GAE")
        backend._connection = conn
        with pytest.raises(RuntimeError, match="no GAE"):
            backend.cluster()
