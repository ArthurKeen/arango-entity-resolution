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


class TestActiveEdgeProjectionAgainstRealDatabase:
    """The suppressed-edge projection, exercised against a live ArangoDB.

    GAE's ``loaddata`` accepts collection names, not queries, so suppressed
    edges are excluded by materialising an active-only edge projection. That
    involves real collection DDL and a real AQL insert, which a fake database
    cannot validate — hence a live-DB test. No GAE engine is required: the
    projection is pure ArangoDB work.
    """

    @pytest.fixture
    def edges(self, db_connection):
        """A similarity edge collection where one edge is suppressed."""
        import uuid

        vtx = f"t_v_{uuid.uuid4().hex[:8]}"
        edge = f"t_e_{uuid.uuid4().hex[:8]}"
        db_connection.create_collection(vtx)
        db_connection.create_collection(edge, edge=True)
        db_connection.collection(vtx).insert_many(
            [{"_key": k} for k in ("a", "b", "c")]
        )
        # a-b is a real match; b-c was rejected by an analyst.
        db_connection.collection(edge).insert_many([
            {"_from": f"{vtx}/a", "_to": f"{vtx}/b", "similarity": 0.95},
            {"_from": f"{vtx}/b", "_to": f"{vtx}/c", "similarity": 0.88,
             "suppressed": True},
        ])
        yield vtx, edge
        for name in (vtx, edge, f"{edge}_gae_active"):
            if db_connection.has_collection(name):
                db_connection.delete_collection(name)

    def test_projection_contains_only_active_edges(self, db_connection, edges):
        _vtx, edge = edges
        backend = GAEWCCBackend(db_connection, edge)

        source = backend._prepare_edge_source()

        assert source == f"{edge}_gae_active"
        assert db_connection.has_collection(source)
        docs = list(db_connection.collection(source).all())
        assert len(docs) == 1, (
            f"expected only the active edge to be projected, got {docs}"
        )
        assert docs[0]["_to"].endswith("/b")
        # The projection must be a real edge collection (type 3), or GAE cannot
        # traverse it.
        assert db_connection.collection(source).properties()["edge"] is True

        backend._drop_temp_edge_collection()
        assert not db_connection.has_collection(source)

    def test_no_projection_when_nothing_suppressed(self, db_connection, edges):
        _vtx, edge = edges
        db_connection.aql.execute(
            "FOR e IN @@c FILTER e.suppressed == true "
            "UPDATE e WITH { suppressed: null } IN @@c",
            bind_vars={"@c": edge},
        )
        backend = GAEWCCBackend(db_connection, edge)

        assert backend._prepare_edge_source() == edge
        assert not db_connection.has_collection(f"{edge}_gae_active")

    def test_stale_projection_is_rebuilt_not_reused(self, db_connection, edges):
        """A leftover projection must never resurrect since-suppressed edges."""
        _vtx, edge = edges
        stale = f"{edge}_gae_active"
        db_connection.create_collection(stale, edge=True)
        db_connection.collection(stale).insert_many([
            {"_from": "ghost/x", "_to": "ghost/y"},
        ])

        backend = GAEWCCBackend(db_connection, edge)
        source = backend._prepare_edge_source()

        docs = list(db_connection.collection(source).all())
        assert len(docs) == 1
        assert "ghost" not in docs[0]["_from"], (
            "stale projection contents survived into the new run"
        )
