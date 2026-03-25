"""Tests for pluggable clustering backends and deprecation shims."""

from __future__ import annotations

import warnings
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from entity_resolution.config.er_config import ClusteringConfig
from entity_resolution.services.clustering_backends.base import ClusteringBackend
from entity_resolution.services.clustering_backends.python_dfs import PythonDFSBackend
from entity_resolution.services.clustering_backends.python_union_find import (
    PythonUnionFindBackend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db(edges: List[Dict[str, str]]):
    """Return a mock db whose aql.execute returns *edges* in the expected shape."""
    db = MagicMock()

    def _execute(query, **kwargs):
        if "RETURN [e._from, e._to]" in query:
            return iter([[e["_from"], e["_to"]] for e in edges])
        if "RETURN {from: e._from, to: e._to}" in query:
            return iter([{"from": e["_from"], "to": e["_to"]} for e in edges])
        return iter([])

    db.aql.execute = _execute
    return db


TRIANGLE_EDGES = [
    {"_from": "col/a", "_to": "col/b"},
    {"_from": "col/b", "_to": "col/c"},
]

TWO_COMPONENT_EDGES = [
    {"_from": "col/a", "_to": "col/b"},
    {"_from": "col/c", "_to": "col/d"},
]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestProtocol:
    def test_dfs_implements_protocol(self):
        db = _make_mock_db([])
        backend = PythonDFSBackend(db, "edges")
        assert isinstance(backend, ClusteringBackend)

    def test_union_find_implements_protocol(self):
        db = _make_mock_db([])
        backend = PythonUnionFindBackend(db, "edges")
        assert isinstance(backend, ClusteringBackend)


# ---------------------------------------------------------------------------
# PythonDFSBackend
# ---------------------------------------------------------------------------

class TestPythonDFSBackend:
    def test_single_component(self):
        db = _make_mock_db(TRIANGLE_EDGES)
        clusters = PythonDFSBackend(db, "edges").cluster()
        assert len(clusters) == 1
        assert sorted(clusters[0]) == ["a", "b", "c"]

    def test_two_components(self):
        db = _make_mock_db(TWO_COMPONENT_EDGES)
        clusters = PythonDFSBackend(db, "edges").cluster()
        assert len(clusters) == 2
        keys = {tuple(sorted(c)) for c in clusters}
        assert ("a", "b") in keys
        assert ("c", "d") in keys

    def test_no_edges(self):
        db = _make_mock_db([])
        assert PythonDFSBackend(db, "edges").cluster() == []

    def test_backend_name(self):
        db = _make_mock_db([])
        assert PythonDFSBackend(db, "edges").backend_name() == "python_dfs"


# ---------------------------------------------------------------------------
# PythonUnionFindBackend
# ---------------------------------------------------------------------------

class TestPythonUnionFindBackend:
    def test_single_component(self):
        db = _make_mock_db(TRIANGLE_EDGES)
        clusters = PythonUnionFindBackend(db, "edges").cluster()
        assert len(clusters) == 1
        assert sorted(clusters[0]) == ["a", "b", "c"]

    def test_two_components(self):
        db = _make_mock_db(TWO_COMPONENT_EDGES)
        clusters = PythonUnionFindBackend(db, "edges").cluster()
        assert len(clusters) == 2
        keys = {tuple(sorted(c)) for c in clusters}
        assert ("a", "b") in keys
        assert ("c", "d") in keys

    def test_no_edges(self):
        db = _make_mock_db([])
        assert PythonUnionFindBackend(db, "edges").cluster() == []

    def test_backend_name(self):
        db = _make_mock_db([])
        assert PythonUnionFindBackend(db, "edges").backend_name() == "python_union_find"


# ---------------------------------------------------------------------------
# Parity: DFS == Union-Find
# ---------------------------------------------------------------------------

class TestParity:
    """DFS and Union-Find must produce identical clusters on the same input."""

    @pytest.mark.parametrize(
        "edges",
        [
            TRIANGLE_EDGES,
            TWO_COMPONENT_EDGES,
            [
                {"_from": "x/1", "_to": "x/2"},
                {"_from": "x/2", "_to": "x/3"},
                {"_from": "x/3", "_to": "x/4"},
                {"_from": "x/5", "_to": "x/6"},
                {"_from": "x/7", "_to": "x/8"},
                {"_from": "x/8", "_to": "x/9"},
                {"_from": "x/9", "_to": "x/7"},
            ],
        ],
        ids=["triangle", "two_components", "mixed_graph"],
    )
    def test_dfs_union_find_produce_same_clusters(self, edges):
        db_dfs = _make_mock_db(edges)
        db_uf = _make_mock_db(edges)

        dfs_clusters = PythonDFSBackend(db_dfs, "edges").cluster()
        uf_clusters = PythonUnionFindBackend(db_uf, "edges").cluster()

        normalise = lambda clusters: sorted(tuple(sorted(c)) for c in clusters)
        assert normalise(dfs_clusters) == normalise(uf_clusters)


# ---------------------------------------------------------------------------
# ClusteringConfig deprecation
# ---------------------------------------------------------------------------

class TestClusteringConfigDeprecation:
    def test_backend_field_accepted(self):
        cfg = ClusteringConfig(backend="python_union_find")
        assert cfg.backend == "python_union_find"

    def test_default_backend_is_python_union_find(self):
        cfg = ClusteringConfig()
        assert cfg.backend == "python_union_find"

    def test_wcc_algorithm_triggers_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cfg = ClusteringConfig(wcc_algorithm="python_dfs")
            assert cfg.backend == "python_dfs"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "wcc_algorithm" in str(w[0].message)

    def test_wcc_algorithm_maps_aql_graph(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            cfg = ClusteringConfig(wcc_algorithm="aql_graph")
            assert cfg.backend == "aql_graph"

    def test_from_dict_reads_backend(self):
        cfg = ClusteringConfig.from_dict({"backend": "python_union_find"})
        assert cfg.backend == "python_union_find"

    def test_from_dict_with_legacy_wcc_algorithm(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            cfg = ClusteringConfig.from_dict({"wcc_algorithm": "python_dfs"})
            assert cfg.backend == "python_dfs"
            assert any("wcc_algorithm" in str(x.message) for x in w)

    def test_to_dict_emits_backend_not_wcc_algorithm(self):
        cfg = ClusteringConfig(backend="python_union_find")
        d = cfg.to_dict()
        assert "backend" in d
        assert d["backend"] == "python_union_find"
        assert "wcc_algorithm" not in d

    def test_validate_accepts_valid_backends(self):
        for name in ("python_dfs", "python_union_find", "aql_graph"):
            cfg = ClusteringConfig(backend=name)
            assert cfg.validate() == []

    def test_validate_rejects_unknown_backend(self):
        cfg = ClusteringConfig(backend="bogus")
        errors = cfg.validate()
        assert len(errors) == 1
        assert "bogus" in errors[0]


# ---------------------------------------------------------------------------
# WCCClusteringService backend dispatch + deprecation
# ---------------------------------------------------------------------------

class TestWCCServiceBackendDispatch:
    def test_backend_param_sets_backend(self):
        from entity_resolution.services.wcc_clustering_service import WCCClusteringService

        db = MagicMock()
        db.has_collection.return_value = True
        db.collection.return_value = MagicMock()

        svc = WCCClusteringService(db=db, backend="python_union_find")
        assert svc.backend == "python_union_find"

    def test_use_bulk_fetch_true_maps_to_python_dfs(self):
        from entity_resolution.services.wcc_clustering_service import WCCClusteringService

        db = MagicMock()
        db.has_collection.return_value = True
        db.collection.return_value = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            svc = WCCClusteringService(db=db, use_bulk_fetch=True)
            assert svc.backend == "python_dfs"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)

    def test_use_bulk_fetch_false_maps_to_aql_graph(self):
        from entity_resolution.services.wcc_clustering_service import WCCClusteringService

        db = MagicMock()
        db.has_collection.return_value = True
        db.collection.return_value = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            svc = WCCClusteringService(db=db, use_bulk_fetch=False)
            assert svc.backend == "aql_graph"
            assert any("use_bulk_fetch" in str(x.message) for x in w)

    def test_backend_used_in_statistics(self):
        from entity_resolution.services.wcc_clustering_service import WCCClusteringService

        db = MagicMock()
        db.has_collection.return_value = True
        db.collection.return_value = MagicMock()

        svc = WCCClusteringService(db=db, backend="python_union_find")
        stats = svc.get_statistics()
        assert stats["backend_used"] == "python_union_find"
