"""Tests for auto backend selection and python_sparse parity."""

from __future__ import annotations

import warnings
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

from entity_resolution.config.er_config import ClusteringConfig
from entity_resolution.services.clustering_backends.python_dfs import PythonDFSBackend
from entity_resolution.services.clustering_backends.python_union_find import (
    PythonUnionFindBackend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db(edges: List[Dict[str, str]]):
    db = MagicMock()

    def _execute(query, **kwargs):
        if "RETURN [e._from, e._to]" in query:
            return iter([[e["_from"], e["_to"]] for e in edges])
        if "RETURN {from: e._from, to: e._to}" in query:
            return iter([{"from": e["_from"], "to": e["_to"]} for e in edges])
        return iter([])

    db.aql.execute = _execute
    return db


MIXED_EDGES = [
    {"_from": "x/1", "_to": "x/2"},
    {"_from": "x/2", "_to": "x/3"},
    {"_from": "x/3", "_to": "x/4"},
    {"_from": "x/5", "_to": "x/6"},
    {"_from": "x/7", "_to": "x/8"},
    {"_from": "x/8", "_to": "x/9"},
    {"_from": "x/9", "_to": "x/7"},
]


# ---------------------------------------------------------------------------
# ClusteringConfig — new defaults and fields
# ---------------------------------------------------------------------------

class TestClusteringConfigV34:
    def test_default_backend_is_python_union_find(self):
        cfg = ClusteringConfig()
        assert cfg.backend == "python_union_find"

    def test_auto_backend_accepted(self):
        cfg = ClusteringConfig(backend="auto")
        assert cfg.validate() == []

    def test_python_sparse_backend_accepted(self):
        cfg = ClusteringConfig(backend="python_sparse")
        assert cfg.validate() == []

    def test_auto_select_threshold_edges_default(self):
        cfg = ClusteringConfig()
        assert cfg.auto_select_threshold_edges == 2_000_000

    def test_sparse_backend_enabled_default(self):
        cfg = ClusteringConfig()
        assert cfg.sparse_backend_enabled is True

    def test_from_dict_reads_new_fields(self):
        cfg = ClusteringConfig.from_dict({
            "backend": "auto",
            "auto_select_threshold_edges": 500_000,
            "sparse_backend_enabled": False,
        })
        assert cfg.backend == "auto"
        assert cfg.auto_select_threshold_edges == 500_000
        assert cfg.sparse_backend_enabled is False


# ---------------------------------------------------------------------------
# WCCClusteringService — auto backend selection
# ---------------------------------------------------------------------------

class TestAutoBackendSelection:
    def _make_service(self, edge_count, backend="auto", sparse_enabled=True, threshold=100):
        from entity_resolution.services.wcc_clustering_service import WCCClusteringService

        db = MagicMock()
        db.has_collection.return_value = True

        edge_coll = MagicMock()
        edge_coll.count.return_value = edge_count
        db.collection.return_value = edge_coll

        return WCCClusteringService(
            db=db,
            backend=backend,
            auto_select_threshold_edges=threshold,
            sparse_backend_enabled=sparse_enabled,
        )

    def test_auto_selects_union_find_below_threshold(self):
        svc = self._make_service(edge_count=50, threshold=100)
        backend = svc._get_backend()
        assert backend.backend_name() == "python_union_find"

    def test_auto_selects_sparse_above_threshold_when_scipy_available(self):
        svc = self._make_service(edge_count=200, threshold=100)
        try:
            import scipy  # noqa: F401
            backend = svc._get_backend()
            assert backend.backend_name() == "python_sparse"
        except ImportError:
            pytest.skip("scipy not installed")

    def test_auto_falls_back_to_union_find_when_sparse_unavailable(self):
        """When sparse_backend_enabled=False, auto always picks union_find even above threshold."""
        svc = self._make_service(edge_count=200, threshold=100, sparse_enabled=False)
        backend = svc._get_backend()
        assert backend.backend_name() == "python_union_find"

    def test_auto_respects_sparse_disabled(self):
        svc = self._make_service(edge_count=200, threshold=100, sparse_enabled=False)
        backend = svc._get_backend()
        assert backend.backend_name() == "python_union_find"

    def test_default_backend_in_statistics(self):
        svc = self._make_service(edge_count=50, backend="python_union_find")
        stats = svc.get_statistics()
        assert stats["backend_used"] == "python_union_find"


# ---------------------------------------------------------------------------
# PythonSparseBackend — parity with Union-Find
# ---------------------------------------------------------------------------

class TestSparseParity:
    @pytest.mark.parametrize(
        "edges",
        [
            [{"_from": "col/a", "_to": "col/b"}, {"_from": "col/b", "_to": "col/c"}],
            [{"_from": "col/a", "_to": "col/b"}, {"_from": "col/c", "_to": "col/d"}],
            MIXED_EDGES,
        ],
        ids=["triangle", "two_components", "mixed_graph"],
    )
    def test_sparse_matches_union_find(self, edges):
        try:
            from entity_resolution.services.clustering_backends.python_sparse import (
                PythonSparseBackend,
            )
        except ImportError:
            pytest.skip("scipy not installed")

        db_uf = _make_mock_db(edges)
        db_sp = _make_mock_db(edges)

        uf_clusters = PythonUnionFindBackend(db_uf, "edges").cluster()
        sp_clusters = PythonSparseBackend(db_sp, "edges").cluster()

        normalise = lambda clusters: sorted(tuple(sorted(c)) for c in clusters)
        assert normalise(uf_clusters) == normalise(sp_clusters)

    def test_sparse_backend_name(self):
        try:
            from entity_resolution.services.clustering_backends.python_sparse import (
                PythonSparseBackend,
            )
        except ImportError:
            pytest.skip("scipy not installed")
        db = _make_mock_db([])
        assert PythonSparseBackend(db, "edges").backend_name() == "python_sparse"
