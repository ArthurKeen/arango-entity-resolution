"""
Unit tests for MCP tools and IncrementalResolver.

All tests use mock DB objects — no live ArangoDB required.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def _make_db(docs=None, edge_docs=None, collection_count=5):
    """Return a lightweight mock ArangoDB database."""
    db = MagicMock()

    # collection() → mock with count()
    coll_mock = MagicMock()
    coll_mock.count.return_value = collection_count
    db.collection.return_value = coll_mock
    db.has_collection.return_value = True

    # aql.execute → returns docs list
    def _aql(query, bind_vars=None, **kwargs):
        if "LOWER(LEFT" in query:
            return iter(docs or [])
        if edge_docs is not None and "ec" in (bind_vars or {}):
            return iter(edge_docs)
        return iter(docs or [])

    db.aql.execute.side_effect = _aql
    return db


# ---------------------------------------------------------------------------
# IncrementalResolver
# ---------------------------------------------------------------------------

class TestIncrementalResolver:
    def test_resolve_returns_matches_above_threshold(self):
        from entity_resolution.core.incremental_resolver import IncrementalResolver

        candidate = {
            "_key": "c1", "_id": "companies/c1",
            "name": "Acme Corporation", "city": "Boston",
        }
        db = _make_db(docs=[candidate])

        resolver = IncrementalResolver(
            db=db,
            collection="companies",
            fields=["name", "city"],
            confidence_threshold=0.80,
        )
        matches = resolver.resolve({"name": "Acme Corp", "city": "Boston"})

        assert isinstance(matches, list)
        # "Acme Corp" vs "Acme Corporation" + "Boston" exact = should score high
        assert all("score" in m for m in matches)
        assert all("field_scores" in m for m in matches)

    def test_resolve_excludes_low_scores(self):
        from entity_resolution.core.incremental_resolver import IncrementalResolver

        unrelated = {
            "_key": "u1", "_id": "companies/u1",
            "name": "XYZ Widgets", "city": "Miami",
        }
        db = _make_db(docs=[unrelated])

        resolver = IncrementalResolver(
            db=db,
            collection="companies",
            fields=["name", "city"],
            confidence_threshold=0.90,
        )
        matches = resolver.resolve({"name": "Acme Corporation", "city": "Boston"})
        assert matches == []

    def test_resolve_respects_top_k(self):
        from entity_resolution.core.incremental_resolver import IncrementalResolver

        # All 5 candidates are identical — all should score 1.0
        candidates = [
            {"_key": f"c{i}", "_id": f"companies/c{i}", "name": "Acme", "city": "Boston"}
            for i in range(5)
        ]
        db = _make_db(docs=candidates)

        resolver = IncrementalResolver(
            db=db, collection="companies", fields=["name", "city"],
            confidence_threshold=0.5,
        )
        matches = resolver.resolve({"name": "Acme", "city": "Boston"}, top_k=3)
        assert len(matches) <= 3

    def test_full_scan_fallback_when_no_blocking_keys(self):
        from entity_resolution.core.incremental_resolver import IncrementalResolver

        candidate = {"_key": "k1", "score_field": 42}  # no text fields
        db = _make_db(docs=[candidate])

        resolver = IncrementalResolver(
            db=db, collection="things", fields=["score_field"],
            confidence_threshold=0.0,
        )
        # Should not raise even with non-string field
        resolver.resolve({"score_field": 42})


# ---------------------------------------------------------------------------
# MCP tool: pipeline_status
# ---------------------------------------------------------------------------

class TestPipelineStatus:
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    @patch("entity_resolution.mcp.tools.pipeline.count_inferred_edges")
    def test_pipeline_status_returns_expected_keys(self, mock_count, mock_get_db):
        from entity_resolution.mcp.tools.pipeline import run_pipeline_status

        mock_db = MagicMock()
        mock_db.has_collection.return_value = True
        mock_db.collection.return_value.count.return_value = 100
        mock_get_db.return_value = mock_db
        mock_count.return_value = {"inferred_edges": 10, "avg_confidence": 0.9}

        result = run_pipeline_status(
            host="localhost", port=8529,
            username="root", password="pass", database="test",
            collection="companies",
        )

        assert result["collection"] == "companies"
        assert result["total_documents"] == 100
        assert "edge_stats" in result
        assert "cluster_count" in result


class TestFindDuplicates:
    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_passes_active_learning_config(self, mock_get_db, mock_pipeline_cls):
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates

        mock_get_db.return_value = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {"ok": True}
        mock_pipeline_cls.return_value = mock_pipeline

        result = run_find_duplicates(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
            fields=["name"],
            enable_active_learning=True,
            feedback_collection="companies_feedback",
            active_learning_refresh_every=5,
            active_learning_model="openrouter/test",
            active_learning_low_threshold=0.6,
            active_learning_high_threshold=0.82,
        )

        cfg = mock_pipeline_cls.call_args.kwargs["config"]
        assert cfg.active_learning.enabled is True
        assert cfg.active_learning.feedback_collection == "companies_feedback"
        assert cfg.active_learning.refresh_every == 5
        assert cfg.active_learning.model == "openrouter/test"
        assert cfg.active_learning.low_threshold == 0.6
        assert cfg.active_learning.high_threshold == 0.82
        assert result["ok"] is True
        assert result["er_options_schema_version"] == "1.0"

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_unresolved_doc_ids")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_request_multistage_execution_updates_stage_metadata(
        self,
        mock_get_db,
        mock_get_unresolved,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_get_db.return_value = MagicMock()
        mock_get_unresolved.side_effect = [
            {"companies/a1", "companies/a2", "companies/a3"},
            {"companies/a2", "companies/a3"},
        ]
        mock_has_any_edges.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.side_effect = [
            [{"doc1_key": "a1", "doc2_key": "a2"}],
            [{"doc1_key": "a2", "doc2_key": "a3"}],
        ]
        mock_pipeline._run_similarity.side_effect = [
            [("a1", "a2", 0.91)],
            [("a2", "a3", 0.82)],
        ]
        mock_pipeline._run_edge_creation.side_effect = [1, 1]
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.85,
            alias_sources=[{"type": "managed_ref", "ref": "missing_ref"}],
            stages=[
                {"type": "bm25", "fields": ["name", "city"], "min_score": 0.9},
                {"type": "embedding", "fields": ["description"], "min_score": 0.78},
            ],
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        first_cfg = mock_pipeline_cls.call_args_list[0].kwargs["config"]
        second_cfg = mock_pipeline_cls.call_args_list[1].kwargs["config"]
        assert first_cfg.blocking.strategy == "bm25"
        assert first_cfg.blocking.fields == ["name", "city"]
        assert first_cfg.similarity.threshold == 0.9
        assert second_cfg.blocking.strategy == "vector"
        assert second_cfg.blocking.fields == ["description"]
        assert second_cfg.similarity.threshold == 0.78

        assert result["stages"]["enabled"] is True
        assert result["stages"]["execution_mode"] == "multi_stage"
        assert result["stages"]["requested_stage_count"] == 2
        assert result["stages"]["gating"]["aliasing"]["managed_ref_requested"] == ["missing_ref"]
        assert result["stages"]["gating"]["aliasing"]["managed_ref_applied"] == []
        assert result["stages"]["gating"]["aliasing"]["managed_ref_missing"] == ["missing_ref"]
        assert len(result["stages"]["stage_results"]) == 2
        assert result["edges"]["edges_created"] == 2

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_single_stage_scaffold_includes_aliasing_in_stage_gating(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {"a1": {"name": "ibm"}, "a2": {"name": "international business machines"}}
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.9)]
        mock_pipeline._run_edge_creation.return_value = 0
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            require_token_overlap=True,
            token_overlap_bypass_score=0.95,
            alias_sources=[{"type": "managed_ref", "ref": "missing_ref"}],
            stages=[{"type": "exact", "fields": ["name"], "min_score": 0.8}],
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["stages"]["execution_mode"] == "single_stage_scaffold"
        assert result["stages"]["gating"]["aliasing"]["managed_ref_requested"] == ["missing_ref"]
        assert result["stages"]["gating"]["aliasing"]["managed_ref_applied"] == []
        assert result["stages"]["gating"]["aliasing"]["managed_ref_missing"] == ["missing_ref"]

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_request_applies_margin_gate(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2"), ("a1", "a3")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.91), ("a1", "a3", 0.88)]
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            min_margin=0.05,
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["edges"]["edges_created"] == 0
        assert result["similarity"]["gates"]["enabled"] is True
        assert result["similarity"]["gates"]["rejected_margin"] >= 1

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_request_applies_token_overlap_gate(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {
            "a1": {"name": "Acme Holdings"},
            "a2": {"name": "Globex Partners"},
        }
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.9)]
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            require_token_overlap=True,
            token_overlap_bypass_score=0.95,
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["edges"]["edges_created"] == 0
        assert result["similarity"]["gates"]["enabled"] is True
        assert result["similarity"]["gates"]["mode"] == "enforce"
        assert result["similarity"]["gates"]["rejected_token_overlap"] == 1

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_report_only_mode_does_not_reject(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {
            "a1": {"name": "Acme Holdings"},
            "a2": {"name": "Globex Partners"},
        }
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.9)]
        mock_pipeline._run_edge_creation.return_value = 1
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            gating_mode="report_only",
            require_token_overlap=True,
            token_overlap_bypass_score=0.95,
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["edges"]["edges_created"] == 1
        assert result["similarity"]["gates"]["mode"] == "report_only"
        assert result["similarity"]["gates"]["enforcement_enabled"] is False
        assert result["similarity"]["gates"]["rejected_token_overlap"] == 0
        assert result["similarity"]["gates"]["would_reject_token_overlap"] == 1

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_request_applies_token_jaccard_similarity_gate(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {
            "a1": {"name": "River Holdings Limited"},
            "a2": {"name": "Sunset Bistro Group"},
        }
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.95)]
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            similarity_type="token_jaccard",
            token_jaccard_fields=["name"],
            token_jaccard_min_score=0.6,
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["edges"]["edges_created"] == 0
        assert result["similarity"]["gates"]["enabled"] is True
        assert result["similarity"]["gates"]["rejected_token_jaccard"] == 1

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_token_overlap_gate_respects_inline_aliases(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {
            "a1": {"name": "ibm"},
            "a2": {"name": "international business machines"},
        }
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.90)]
        mock_pipeline._run_edge_creation.return_value = 1
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            require_token_overlap=True,
            token_overlap_bypass_score=0.95,
            alias_sources=[
                {"type": "inline", "map": {"ibm": ["international", "business", "machines"]}},
            ],
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["edges"]["edges_created"] == 1
        assert result["similarity"]["gates"]["rejected_token_overlap"] == 0

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_reports_missing_managed_ref_alias(self, mock_get_db, mock_has_any_edges, mock_pipeline_cls):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest, MCPOptions
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {"a1": {"name": "ibm"}, "a2": {"name": "international business machines"}}
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.90)]
        mock_pipeline._run_edge_creation.return_value = 1
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            gating_mode="report_only",
            require_token_overlap=True,
            token_overlap_bypass_score=0.95,
            alias_sources=[{"type": "managed_ref", "ref": "missing_ref"}],
            options=MCPOptions(aliasing={"managed_refs": {"other_ref": {"ibm": ["international"]}}}),
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_requested"] == ["missing_ref"]
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_applied"] == []
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_missing"] == ["missing_ref"]

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_token_overlap_gate_respects_managed_ref_aliases(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest, MCPOptions
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {
            "a1": {"name": "ibm"},
            "a2": {"name": "international business machines"},
        }
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.90)]
        mock_pipeline._run_edge_creation.return_value = 1
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            require_token_overlap=True,
            token_overlap_bypass_score=0.95,
            alias_sources=[{"type": "managed_ref", "ref": "entity_aliases_v1"}],
            options=MCPOptions(
                aliasing={
                    "managed_refs": {
                        "entity_aliases_v1": {
                            "ibm": ["international", "business", "machines"],
                        }
                    }
                }
            ),
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["edges"]["edges_created"] == 1
        assert result["similarity"]["gates"]["rejected_token_overlap"] == 0
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_requested"] == ["entity_aliases_v1"]
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_applied"] == ["entity_aliases_v1"]
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_missing"] == []

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_request_applies_type_affinity_gate(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_coll = MagicMock()
        docs = {
            "a1": {"name": "River Bank Group", "type": "organization"},
            "a2": {"name": "River Bistro", "type": "restaurant"},
        }
        mock_coll.get.side_effect = lambda key: docs.get(key)
        mock_db.collection.return_value = mock_coll
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = [("a1", "a2")]
        mock_pipeline._run_similarity.return_value = [("a1", "a2", 0.96)]
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            token_type_affinity={"bank": ["financial_institution"]},
            target_type_field="type",
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["edges"]["edges_created"] == 0
        assert result["similarity"]["gates"]["enabled"] is True
        assert result["similarity"]["gates"]["rejected_type_affinity"] == 1

    @patch("entity_resolution.core.configurable_pipeline.ConfigurableERPipeline")
    @patch("entity_resolution.mcp.tools.pipeline._has_any_edges")
    @patch("entity_resolution.mcp.tools.pipeline._get_db")
    def test_find_duplicates_no_matches_still_surfaces_aliasing_diagnostics(
        self,
        mock_get_db,
        mock_has_any_edges,
        mock_pipeline_cls,
    ):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import run_find_duplicates_request

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_has_any_edges.return_value = False

        mock_pipeline = MagicMock()
        mock_pipeline._run_blocking.return_value = []
        mock_pipeline._run_similarity.return_value = []
        mock_pipeline._run_edge_creation.return_value = 0
        mock_pipeline_cls.return_value = mock_pipeline

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            require_token_overlap=True,
            alias_sources=[{"type": "managed_ref", "ref": "missing_ref"}],
        )
        result = run_find_duplicates_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["similarity"]["gates"]["enabled"] is True
        assert result["similarity"]["gates"]["input_matches"] == 0
        assert result["similarity"]["gates"]["accepted_matches"] == 0
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_requested"] == ["missing_ref"]
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_applied"] == []
        assert result["similarity"]["gates"]["aliasing"]["managed_ref_missing"] == ["missing_ref"]

    def test_apply_precision_gates_without_rules_surfaces_aliasing_diagnostics(self):
        from entity_resolution.mcp.contracts import FindDuplicatesRequest
        from entity_resolution.mcp.tools.pipeline import _apply_precision_gates

        req = FindDuplicatesRequest(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            alias_sources=[{"type": "managed_ref", "ref": "missing_ref"}],
        )
        accepted, gate_stats = _apply_precision_gates(
            db=None,
            collection="companies",
            matches=[("a1", "a2", 0.9)],
            fields=["name"],
            request=req,
        )

        assert len(accepted) == 1
        assert gate_stats["enabled"] is False
        assert gate_stats["input_matches"] == 1
        assert gate_stats["accepted_matches"] == 1
        assert gate_stats["aliasing"]["managed_ref_requested"] == ["missing_ref"]
        assert gate_stats["aliasing"]["managed_ref_applied"] == []
        assert gate_stats["aliasing"]["managed_ref_missing"] == ["missing_ref"]


# ---------------------------------------------------------------------------
# MCP tool: explain_match
# ---------------------------------------------------------------------------

class TestExplainMatch:
    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_returns_breakdown(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "Acme Corporation", "city": "Boston"}
        doc_b = {"_key": "b1", "name": "Acme Corp", "city": "Boston"}

        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False  # no existing edges
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_explain_match(
            host="localhost", port=8529,
            username="root", password="pass", database="test",
            collection="companies", key_a="a1", key_b="b1",
        )

        assert "overall_score" in result
        assert "field_breakdown" in result
        assert result["overall_score"] > 0
        assert "name" in result["field_breakdown"]
        assert "city" in result["field_breakdown"]
        assert result["interpretation"] in {
            "strong match", "probable match", "uncertain", "likely different"
        }
        assert "gates" not in result

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_missing_doc(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [None, None]
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_explain_match(
            host="localhost", port=8529,
            username="root", password="pass", database="test",
            collection="companies", key_a="bad_key", key_b="b1",
        )
        assert "error" in result

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_includes_gate_failures(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "River Bank Group", "type": "organization"}
        doc_b = {"_key": "b1", "name": "Sunset Bistro", "type": "restaurant"}

        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_explain_match(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
            key_a="a1",
            key_b="b1",
            fields=["name"],
            options={
                "similarity": {"confidence_threshold": 0.95},
                "gating": {
                    "min_margin": 0.05,
                    "require_token_overlap": True,
                    "token_overlap_bypass_score": 0.99,
                    "token_type_affinity": {"bank": ["financial_institution"]},
                    "target_type_field": "type",
                },
                "aliasing": {
                    "sources": [
                        {"type": "inline", "map": {"bank": ["finance"]}},
                        {"type": "acronym", "auto": True, "min_word_len": 3},
                    ]
                },
            },
        )

        assert "gates" in result
        gates = result["gates"]
        assert gates["summary"]["all_passed"] is False
        assert gates["summary"]["mode"] == "enforce"
        failures = [f["gate"] for f in gates["summary"]["gate_failures"]]
        assert "score_threshold" in failures
        assert "margin" in failures
        assert "token_overlap" in failures
        assert "type_affinity" in failures
        assert gates["type_affinity"]["candidate_type"] == "restaurant"
        assert gates["aliasing"]["configured"] is True
        assert gates["aliasing"]["inline_alias_count"] == 1
        assert gates["token_jaccard"]["configured"] is False

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_token_jaccard_similarity_failure(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "Alpha Risk Corp"}
        doc_b = {"_key": "b1", "name": "Sunset Bistro LLC"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_explain_match(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
            key_a="a1",
            key_b="b1",
            fields=["name"],
            options={
                "similarity": {
                    "type": "token_jaccard",
                    "token_jaccard_fields": ["name"],
                    "token_jaccard_min_score": 0.8,
                }
            },
        )
        failures = [f["gate"] for f in result["gates"]["summary"]["gate_failures"]]
        assert "token_jaccard" in failures
        assert result["gates"]["token_jaccard"]["configured"] is True

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_token_overlap_uses_managed_ref_aliases(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_explain_match(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
            key_a="a1",
            key_b="b1",
            fields=["name"],
            options={
                "gating": {
                    "require_token_overlap": True,
                    "token_overlap_bypass_score": 0.99,
                },
                "aliasing": {
                    "sources": [{"type": "managed_ref", "ref": "entity_aliases_v1"}],
                    "managed_refs": {
                        "entity_aliases_v1": {
                            "ibm": ["international", "business", "machines"],
                        }
                    },
                },
            },
        )
        failures = [f["gate"] for f in result["gates"]["summary"]["gate_failures"]]
        assert "token_overlap" not in failures
        assert result["gates"]["aliasing"]["managed_ref_requested"] == ["entity_aliases_v1"]
        assert result["gates"]["aliasing"]["managed_ref_applied"] == ["entity_aliases_v1"]
        assert result["gates"]["aliasing"]["managed_ref_missing"] == []

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_reports_missing_managed_ref_alias(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_explain_match(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
            key_a="a1",
            key_b="b1",
            fields=["name"],
            options={
                "gating": {
                    "require_token_overlap": True,
                    "token_overlap_bypass_score": 0.99,
                },
                "aliasing": {
                    "sources": [{"type": "managed_ref", "ref": "missing_ref"}],
                    "managed_refs": {"other_ref": {"ibm": ["international"]}},
                },
            },
        )

        assert result["gates"]["aliasing"]["managed_ref_requested"] == ["missing_ref"]
        assert result["gates"]["aliasing"]["managed_ref_applied"] == []
        assert result["gates"]["aliasing"]["managed_ref_missing"] == ["missing_ref"]
        failures = [f["gate"] for f in result["gates"]["summary"]["gate_failures"]]
        assert "token_overlap" in failures

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_non_list_aliasing_sources(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="options.aliasing.sources must be an array/list"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={"aliasing": {"sources": {"type": "managed_ref", "ref": "entity_aliases_v1"}}},
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_non_object_alias_source_entry(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="options.aliasing.sources\\[0\\] must be an object/dict"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={"aliasing": {"sources": ["managed_ref"]}},
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_alias_source_without_type(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="options.aliasing.sources\\[0\\]\\.type is required"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={"aliasing": {"sources": [{}]}},
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_non_object_inline_alias_map(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="options.aliasing.sources\\[0\\]\\.map must be an object/dict"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={"aliasing": {"sources": [{"type": "inline", "map": ["bad"]}]}},
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_field_alias_source_without_field(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="options.aliasing.sources\\[0\\]\\.field is required for type=field"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={"aliasing": {"sources": [{"type": "field"}]}},
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_non_object_managed_refs(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="options.aliasing.managed_refs must be an object/dict"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={
                    "aliasing": {
                        "sources": [{"type": "managed_ref", "ref": "entity_aliases_v1"}],
                        "managed_refs": ["bad"],
                    }
                },
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_non_object_managed_ref_entry(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="options.aliasing.managed_refs.entity_aliases_v1 must be an object/dict"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={
                    "aliasing": {
                        "sources": [{"type": "managed_ref", "ref": "entity_aliases_v1"}],
                        "managed_refs": {"entity_aliases_v1": ["bad"]},
                    }
                },
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_managed_ref_without_ref(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="\\.ref is required for type=managed_ref"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={"aliasing": {"sources": [{"type": "managed_ref"}]}},
            )

    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    def test_explain_match_rejects_unknown_alias_source_type(self, mock_client_cls):
        from entity_resolution.mcp.tools.entity import run_explain_match

        doc_a = {"_key": "a1", "name": "ibm"}
        doc_b = {"_key": "b1", "name": "international business machines"}
        mock_db = MagicMock()
        mock_db.collection.return_value.get.side_effect = [doc_a, doc_b]
        mock_db.has_collection.return_value = False
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="must be one of inline, field, acronym, managed_ref"):
            run_explain_match(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                key_a="a1",
                key_b="b1",
                fields=["name"],
                options={"aliasing": {"sources": [{"type": "taxonomy"}]}},
            )


class TestResolveEntityCrossCollection:
    @patch("entity_resolution.mcp.tools.entity.ArangoClient")
    @patch("entity_resolution.services.cross_collection_matching_service.CrossCollectionMatchingService")
    def test_run_resolve_cross_collection_request_with_guardrails(self, mock_service_cls, mock_client_cls):
        from entity_resolution.mcp.normalization import normalize_cross_collection_args
        from entity_resolution.mcp.tools.entity import run_resolve_cross_collection_request

        mock_db = MagicMock()
        mock_client_cls.return_value.db.return_value = mock_db
        mock_service = MagicMock()
        mock_service.match_entities.return_value = {"edges_created": 12, "source_records_processed": 100}
        mock_service_cls.return_value = mock_service

        req = normalize_cross_collection_args(
            source_collection="registrations",
            target_collection="companies",
            source_fields=["company_name", "city"],
            target_fields=["legal_name", "location_city"],
            options={
                "retrieval": {
                    "candidate_limit": 250,
                    "deterministic_tiebreak": True,
                    "target_filter": {"status": {"equals": "active"}},
                    "source_skip_values": {"company_name": ["UNKNOWN"]},
                },
                "execution": {"batch_size": 50, "max_runtime_ms": 120000},
                "similarity": {"confidence_threshold": 0.9},
                "blocking": {"fields": ["company_name"], "strategy": "exact", "use_bm25": False},
                "diagnostics": {"return_diagnostics": True},
            },
        )
        result = run_resolve_cross_collection_request(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            request=req,
        )

        assert result["source_collection"] == "registrations"
        assert result["target_collection"] == "companies"
        assert result["execution_guardrails"]["candidate_limit"] == 250
        assert result["execution_guardrails"]["batch_size"] == 50
        assert result["execution_guardrails"]["max_runtime_ms"] == 120000
        assert result["stats"]["edges_created"] == 12
        assert "diagnostics" in result

        configure_kwargs = mock_service.configure_matching.call_args.kwargs
        assert configure_kwargs["source_fields"] == {"company_name": "company_name", "city": "city"}
        assert configure_kwargs["target_fields"] == {"company_name": "legal_name", "city": "location_city"}
        assert configure_kwargs["blocking_fields"] == ["company_name"]

        match_kwargs = mock_service.match_entities.call_args.kwargs
        assert match_kwargs["threshold"] == 0.9
        assert match_kwargs["limit"] == 250
        assert match_kwargs["batch_size"] == 50
        assert match_kwargs["max_runtime_seconds"] == 120.0
        assert match_kwargs["deterministic_tiebreak"] is True

    def test_run_resolve_entity_cross_collection_rejects_mismatched_fields_without_mapping(self):
        from entity_resolution.mcp.tools.entity import run_resolve_entity_cross_collection

        with pytest.raises(ValueError, match="same length"):
            run_resolve_entity_cross_collection(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                source_collection="source",
                target_collection="target",
                source_fields=["name"],
                target_fields=["name", "city"],
                options={},
            )


# ---------------------------------------------------------------------------
# MCP tool: list_collections
# ---------------------------------------------------------------------------

class TestListCollections:
    @patch("entity_resolution.mcp.tools.cluster.ArangoClient")
    def test_returns_non_system_collections(self, mock_client_cls):
        from entity_resolution.mcp.tools.cluster import run_list_collections

        mock_db = MagicMock()
        mock_db.collections.return_value = [
            {"name": "companies", "system": False, "type": 2},
            {"name": "_system_col", "system": True, "type": 2},
            {"name": "similarity_edges", "system": False, "type": 3},
        ]
        mock_db.collection.return_value.count.return_value = 42
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_list_collections(
            host="localhost", port=8529,
            username="root", password="pass", database="test",
        )

        names = [c["name"] for c in result]
        assert "companies" in names
        assert "_system_col" not in names
        assert any(c["type"] == "edge" for c in result)


# ---------------------------------------------------------------------------
# MCP tool: get_clusters
# ---------------------------------------------------------------------------

class TestGetClusters:
    @patch("entity_resolution.mcp.tools.cluster.ArangoClient")
    def test_get_clusters_returns_quality_fields_when_present(self, mock_client_cls):
        from entity_resolution.mcp.tools.cluster import run_get_clusters

        mock_db = MagicMock()
        mock_db.has_collection.side_effect = lambda name: name == "companies_clusters"
        mock_db.aql.execute.return_value = iter([
            {
                "cluster_id": "cluster_000001",
                "members": ["companies/a1", "companies/b1"],
                "size": 2,
                "representative": "companies/a1",
                "edge_count": 1,
                "average_similarity": 0.91,
                "min_similarity": 0.91,
                "max_similarity": 0.91,
                "density": 1.0,
                "quality_score": 0.946,
            }
        ])
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_get_clusters(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
        )

        assert result[0]["edge_count"] == 1
        assert result[0]["average_similarity"] == 0.91
        assert result[0]["density"] == 1.0
        assert "quality_score" in result[0]

    @patch("entity_resolution.mcp.tools.cluster.ArangoClient")
    def test_get_clusters_preserves_older_docs_without_quality_fields(self, mock_client_cls):
        from entity_resolution.mcp.tools.cluster import run_get_clusters

        mock_db = MagicMock()
        mock_db.has_collection.side_effect = lambda name: name == "companies_clusters"
        mock_db.aql.execute.return_value = iter([
            {
                "cluster_id": "cluster_000001",
                "members": ["companies/a1", "companies/b1"],
                "size": 2,
                "representative": None,
                "edge_count": None,
                "average_similarity": None,
                "min_similarity": None,
                "max_similarity": None,
                "density": None,
                "quality_score": None,
            }
        ])
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_get_clusters(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
        )

        assert result[0]["edge_count"] is None
        assert result[0]["average_similarity"] is None
        assert result[0]["quality_score"] is None

    @patch("entity_resolution.mcp.tools.cluster.ArangoClient")
    def test_get_clusters_fallback_includes_similarity_stats(self, mock_client_cls):
        from entity_resolution.mcp.tools.cluster import run_get_clusters

        mock_db = MagicMock()
        mock_db.has_collection.side_effect = lambda name: name == "companies_similarity_edges"
        mock_db.aql.execute.return_value = iter([
            {
                "vertices": ["companies/a1", "companies/b1"],
                "edge_count": 1,
                "average_similarity": 0.88,
                "min_similarity": 0.88,
                "max_similarity": 0.88,
            }
        ])
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_get_clusters(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
        )

        assert result[0]["stats"][0]["average_similarity"] == 0.88
        assert result[0]["stats"][0]["min_similarity"] == 0.88


# ---------------------------------------------------------------------------
# MCP tool: merge_entities
# ---------------------------------------------------------------------------

class TestMergeEntities:
    @patch("entity_resolution.mcp.tools.cluster.ArangoClient")
    def test_merge_entities_uses_most_complete_and_backfills_missing_fields(self, mock_client_cls):
        from entity_resolution.mcp.tools.cluster import run_merge_entities

        doc_a = {"_key": "a1", "_id": "companies/a1", "name": "Acme", "phone": "6175551234"}
        doc_b = {"_key": "b1", "_id": "companies/b1", "name": "Acme Corp", "city": "Boston", "email": "hello@acme.com"}

        mock_coll = MagicMock()
        mock_coll.get.side_effect = [doc_a, doc_b]

        mock_db = MagicMock()
        mock_db.collection.return_value = mock_coll
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_merge_entities(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
            entity_keys=["a1", "b1"],
            strategy="most_complete",
        )

        assert result["canonical_key"] == "b1"
        assert result["strategy_used"] == "most_complete"
        assert result["golden_record"]["name"] == "Acme Corp"
        assert result["golden_record"]["phone"] == "6175551234"
        assert result["golden_record"]["city"] == "Boston"

    @patch("entity_resolution.mcp.tools.cluster.ArangoClient")
    def test_merge_entities_newest_prefers_latest_timestamp(self, mock_client_cls):
        from entity_resolution.mcp.tools.cluster import run_merge_entities

        older = {"_key": "a1", "_id": "companies/a1", "name": "Acme", "updatedAt": "2026-03-01T10:00:00Z"}
        newer = {"_key": "b1", "_id": "companies/b1", "name": "Acme Corporation", "updatedAt": "2026-03-05T12:30:00Z"}

        mock_coll = MagicMock()
        mock_coll.get.side_effect = [older, newer]

        mock_db = MagicMock()
        mock_db.collection.return_value = mock_coll
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_merge_entities(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            collection="companies",
            entity_keys=["a1", "b1"],
            strategy="newest",
        )

        assert result["canonical_key"] == "b1"
        assert result["golden_record"]["name"] == "Acme Corporation"

    @patch("entity_resolution.mcp.tools.cluster.ArangoClient")
    def test_merge_entities_rejects_missing_docs(self, mock_client_cls):
        from entity_resolution.mcp.tools.cluster import run_merge_entities

        mock_coll = MagicMock()
        mock_coll.get.side_effect = [None]

        mock_db = MagicMock()
        mock_db.collection.return_value = mock_coll
        mock_client_cls.return_value.db.return_value = mock_db

        with pytest.raises(ValueError, match="Documents not found"):
            run_merge_entities(
                host="localhost",
                port=8529,
                username="root",
                password="pass",
                database="test",
                collection="companies",
                entity_keys=["missing"],
            )


# ---------------------------------------------------------------------------
# MCP advisor tools
# ---------------------------------------------------------------------------

class TestAdvisorTools:
    @patch("entity_resolution.mcp.tools.advisor.ArangoClient")
    def test_profile_dataset_returns_field_profiles(self, mock_client_cls):
        from entity_resolution.mcp.tools.advisor import run_profile_dataset

        mock_db = MagicMock()
        mock_db.has_collection.return_value = True
        mock_db.collection.return_value.count.return_value = 3
        mock_db.aql.execute.return_value = iter(
            [
                {"_key": "1", "name": "Acme Corp", "city": "Boston", "postal_code": "02110"},
                {"_key": "2", "name": "Acme Corporation", "city": "Boston", "postal_code": "02110"},
                {"_key": "3", "name": "Globex", "city": "Austin", "postal_code": "78701"},
            ]
        )
        mock_client_cls.return_value.db.return_value = mock_db

        result = run_profile_dataset(
            host="localhost",
            port=8529,
            username="root",
            password="pass",
            database="test",
            source_type="collection",
            dataset_id="companies",
            request_id="req-profile-001",
            sample_limit=1000,
        )

        assert result["status"] == "ok"
        assert result["tool_version"] == "1.0.0"
        assert result["advisor_policy_version"] == "2026-03-01"
        assert result["er_options_schema_version"] == "1.0"
        assert result["request_id"] == "req-profile-001"
        payload = result["result"]
        assert payload["row_count_estimate"] == 3
        assert payload["sample_size"] == 3
        names = [fp["field"] for fp in payload["field_profiles"]]
        assert "name" in names
        assert "city" in names
        assert "pairwise_signals" in payload

    def test_recommend_blocking_candidates_returns_ranked_candidates(self):
        from entity_resolution.mcp.tools.advisor import run_recommend_blocking_candidates

        profile = {
            "row_count_estimate": 10000,
            "pairwise_signals": {"hub_risk_score": 0.2},
            "field_profiles": [
                {"field": "name", "data_type": "string", "null_rate": 0.01, "entropy_estimate": 0.9},
                {"field": "city", "data_type": "string", "null_rate": 0.02, "entropy_estimate": 0.7},
                {"field": "postal_code", "data_type": "string", "null_rate": 0.01, "entropy_estimate": 0.8},
                {"field": "revenue", "data_type": "number", "null_rate": 0.05, "entropy_estimate": 0.5},
            ],
        }

        result = run_recommend_blocking_candidates(
            profile=profile,
            request_id="req-blocking-001",
            max_composite_size=2,
            max_results=5,
        )

        assert result["status"] == "ok"
        assert result["tool_version"] == "1.0.0"
        assert result["advisor_policy_version"] == "2026-03-01"
        assert result["request_id"] == "req-blocking-001"
        assert "blocking_candidates" in result["result"]
        assert len(result["result"]["blocking_candidates"]) > 0
        top = result["result"]["blocking_candidates"][0]
        assert "fields" in top
        assert "fit_score" in top
        assert "estimated_candidate_pairs" in top

    def test_recommend_resolution_strategy_returns_ranked_recommendations(self):
        from entity_resolution.mcp.tools.advisor import run_recommend_resolution_strategy

        profile = {
            "row_count_estimate": 250000,
            "sample_size": 5000,
            "pairwise_signals": {
                "near_duplicate_rate_estimate": 0.12,
                "hub_risk_score": 0.27,
            },
            "field_profiles": [
                {"field": "name", "data_type": "string", "null_rate": 0.02, "entropy_estimate": 0.83},
                {"field": "address", "data_type": "string", "null_rate": 0.08, "entropy_estimate": 0.71},
                {"field": "postal_code", "data_type": "string", "null_rate": 0.01, "entropy_estimate": 0.62},
            ],
        }
        objective_profile = {
            "priority": "throughput_first",
            "latency_budget_ms": 120,
            "max_edge_count": 150000,
        }

        result = run_recommend_resolution_strategy(
            profile=profile,
            objective_profile=objective_profile,
            request_id="req-strategy-001",
            allow_embedding_models=True,
            allow_graph_clustering=True,
        )

        assert result["status"] == "ok"
        assert result["tool_version"] == "1.0.0"
        assert result["advisor_policy_version"] == "2026-03-01"
        assert result["request_id"] == "req-strategy-001"
        recommendations = result["result"]["recommendations"]
        assert len(recommendations) >= 3
        assert recommendations[0]["rank"] == 1
        assert recommendations[0]["fit_score"] >= recommendations[-1]["fit_score"]
        assert "expected_tradeoffs" in recommendations[0]
        assert "rationale" in recommendations[0]
        assert "confidence" in recommendations[0]

    def test_recommend_resolution_strategy_honors_embedding_toggle(self):
        from entity_resolution.mcp.tools.advisor import run_recommend_resolution_strategy

        result = run_recommend_resolution_strategy(
            profile={"field_profiles": [], "pairwise_signals": {}},
            objective_profile={"priority": "balanced"},
            allow_embedding_models=False,
            allow_graph_clustering=False,
        )

        strategy_ids = [r["strategy_id"] for r in result["result"]["recommendations"]]
        assert "embedding_first_nearest_neighbor" not in strategy_ids
        assert "graph_first_collective_resolution" not in strategy_ids

    def test_estimate_feature_weights_returns_weights_and_threshold(self):
        from entity_resolution.mcp.tools.advisor import run_estimate_feature_weights

        rows = []
        for i in range(1200):
            is_match = i % 2 == 0
            rows.append(
                {
                    "label": 1 if is_match else 0,
                    "features": {
                        "name_jaro_winkler": 0.92 if is_match else 0.42,
                        "address_cosine": 0.88 if is_match else 0.5,
                        "postal_exact": 1.0 if is_match else 0.2,
                    },
                }
            )

        result = run_estimate_feature_weights(
            feature_matrix_ref={"dataset_id": "pair_features_demo", "rows": rows},
            target_metric="f1",
            min_samples=1000,
            request_id="req-weights-001",
        )

        assert result["status"] == "ok"
        assert result["request_id"] == "req-weights-001"
        assert result["tool_version"] == "1.0.0"
        payload = result["result"]
        assert "weights" in payload
        assert "threshold_recommendation" in payload
        assert "diagnostics" in payload
        assert "confidence" in payload
        assert payload["diagnostics"]["samples_used"] == 1200
        assert payload["threshold_recommendation"]["match_threshold"] >= 0.0
        assert payload["threshold_recommendation"]["match_threshold"] <= 1.0
        assert abs(sum(payload["weights"].values()) - 1.0) <= 0.02

    def test_estimate_feature_weights_returns_not_enough_data_error(self):
        from entity_resolution.mcp.tools.advisor import run_estimate_feature_weights

        result = run_estimate_feature_weights(
            feature_matrix_ref={"dataset_id": "pair_features_demo", "rows": []},
            target_metric="f1",
            min_samples=1000,
            request_id="req-weights-002",
        )

        assert result["status"] == "error"
        assert result["request_id"] == "req-weights-002"
        assert result["error"]["code"] == "NOT_ENOUGH_DATA"

    def test_simulate_pipeline_variants_returns_ranked_variants_and_winner(self):
        from entity_resolution.mcp.tools.advisor import run_simulate_pipeline_variants

        variants = [
            {
                "variant_id": "v_blocking_strict",
                "config": {
                    "blocking": {"fields": ["name", "postal_code"], "max_block_size": 80},
                    "matching": {"threshold": 0.86},
                    "embedding": {"enabled": False},
                    "graph": {"enabled": False},
                },
            },
            {
                "variant_id": "v_embedding_graph",
                "config": {
                    "blocking": {"fields": ["name", "city", "postal_code"], "max_block_size": 220},
                    "matching": {"threshold": 0.78},
                    "embedding": {"enabled": True},
                    "graph": {"enabled": True},
                },
            },
        ]

        result = run_simulate_pipeline_variants(
            variants=variants,
            objective_profile={"priority": "throughput_first", "max_memory_mb": 1800},
            request_id="req-sim-001",
        )

        assert result["status"] == "ok"
        assert result["request_id"] == "req-sim-001"
        payload = result["result"]
        assert len(payload["variant_results"]) == 2
        assert len(payload["ranking"]) == 2
        assert payload["ranking"][0]["rank"] == 1
        assert "variant_id" in payload["winner"]
        assert "reason" in payload["winner"]
        assert payload["ranking"][0]["fit_score"] >= payload["ranking"][1]["fit_score"]

    def test_simulate_pipeline_variants_requires_at_least_two_variants(self):
        from entity_resolution.mcp.tools.advisor import run_simulate_pipeline_variants

        result = run_simulate_pipeline_variants(
            variants=[{"variant_id": "v1", "config": {}}],
            objective_profile={"priority": "balanced"},
            request_id="req-sim-002",
        )

        assert result["status"] == "error"
        assert result["request_id"] == "req-sim-002"
        assert result["error"]["code"] == "INVALID_ARGUMENT"

    def test_export_recommended_config_returns_yaml_artifact(self):
        from entity_resolution.mcp.tools.advisor import run_export_recommended_config

        recommendation = {
            "strategy_id": "hybrid_block_then_weighted_match",
            "fit_score": 0.91,
            "rationale": ["Good quality/runtime balance"],
            "expected_tradeoffs": {"precision": "high", "recall": "medium_high"},
            "blocking": {"fields": ["name", "postal_code"], "max_block_size": 80},
            "matching": {"threshold": 0.84, "weights": {"name_jaro_winkler": 0.4, "postal_exact": 0.2}},
        }

        result = run_export_recommended_config(
            recommendation=recommendation,
            format="yaml",
            include_rationale=True,
            request_id="req-export-001",
        )

        assert result["status"] == "ok"
        assert result["request_id"] == "req-export-001"
        payload = result["result"]
        assert payload["format"] == "yaml"
        assert payload["config_hash"].startswith("sha256:")
        assert payload["policy_version"] == "2026-03-01"
        assert "entity_resolution:" in payload["config_text"]

    def test_export_recommended_config_rejects_invalid_format(self):
        from entity_resolution.mcp.tools.advisor import run_export_recommended_config

        result = run_export_recommended_config(
            recommendation={"strategy_id": "hybrid_block_then_weighted_match"},
            format="toml",
            request_id="req-export-002",
        )

        assert result["status"] == "error"
        assert result["request_id"] == "req-export-002"
        assert result["error"]["code"] == "INVALID_ARGUMENT"

    def test_evaluate_blocking_plan_returns_distribution_risks_and_guardrails(self):
        from entity_resolution.mcp.tools.advisor import run_evaluate_blocking_plan

        profile = {
            "row_count_estimate": 125000,
            "pairwise_signals": {"hub_risk_score": 0.24},
            "field_profiles": [
                {"field": "name", "data_type": "string", "null_rate": 0.03, "entropy_estimate": 0.84},
                {"field": "postal_code", "data_type": "string", "null_rate": 0.02, "entropy_estimate": 0.62},
                {"field": "city", "data_type": "string", "null_rate": 0.07, "entropy_estimate": 0.58},
            ],
        }
        blocking_plan = {
            "fields": ["name", "postal_code"],
            "min_block_size": 2,
            "max_block_size": 120,
        }

        result = run_evaluate_blocking_plan(
            profile=profile,
            blocking_plan=blocking_plan,
            request_id="req-eval-blocking-001",
        )

        assert result["status"] == "ok"
        assert result["request_id"] == "req-eval-blocking-001"
        payload = result["result"]
        assert payload["estimated_block_count"] > 0
        assert payload["estimated_candidate_pairs"] > 0
        assert "estimated_block_size_distribution" in payload
        assert "risk_flags" in payload
        assert "recommended_guardrails" in payload
        assert payload["recommended_guardrails"]["suggested_max_block_size"] <= 120

    def test_evaluate_blocking_plan_rejects_unknown_fields(self):
        from entity_resolution.mcp.tools.advisor import run_evaluate_blocking_plan

        profile = {
            "row_count_estimate": 5000,
            "field_profiles": [
                {"field": "name", "data_type": "string", "null_rate": 0.0, "entropy_estimate": 0.8},
            ],
        }

        result = run_evaluate_blocking_plan(
            profile=profile,
            blocking_plan={"fields": ["name", "postalcode"]},
            request_id="req-eval-blocking-002",
        )

        assert result["status"] == "error"
        assert result["request_id"] == "req-eval-blocking-002"
        assert result["error"]["code"] == "INVALID_ARGUMENT"


class TestMcpServerOptionsCompatibility:
    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_options_override_legacy(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {"ok": True}
        server.find_duplicates(
            collection="companies",
            fields=["name"],
            strategy="exact",
            confidence_threshold=0.8,
            max_block_size=500,
            options={
                "blocking": {"strategy": "bm25", "max_block_size": 120, "fields": ["name", "postal_code"]},
                "similarity": {"confidence_threshold": 0.93},
            },
        )

        kwargs = mock_run_find_duplicates.call_args.kwargs
        req = kwargs["request"]
        assert req.collection == "companies"
        assert req.strategy == "bm25"
        assert req.fields == ["name", "postal_code"]
        assert req.confidence_threshold == 0.93
        assert req.max_block_size == 120

    def test_server_find_duplicates_rejects_non_list_aliasing_sources(self):
        from entity_resolution.mcp import server

        with pytest.raises(ValueError, match="options.aliasing.sources must be an array/list"):
            server.find_duplicates(
                collection="companies",
                fields=["name"],
                options={"aliasing": {"sources": {"type": "managed_ref", "ref": "entity_aliases_v1"}}},
            )

    def test_server_find_duplicates_rejects_non_object_managed_refs(self):
        from entity_resolution.mcp import server

        with pytest.raises(ValueError, match="options.aliasing.managed_refs must be an object/dict"):
            server.find_duplicates(
                collection="companies",
                fields=["name"],
                options={
                    "aliasing": {
                        "sources": [{"type": "managed_ref", "ref": "entity_aliases_v1"}],
                        "managed_refs": ["bad"],
                    }
                },
            )

    def test_server_find_duplicates_rejects_managed_ref_without_ref(self):
        from entity_resolution.mcp import server

        with pytest.raises(ValueError, match="\\.ref is required for type=managed_ref"):
            server.find_duplicates(
                collection="companies",
                fields=["name"],
                options={"aliasing": {"sources": [{"type": "managed_ref"}]}},
            )

    @patch("entity_resolution.mcp.tools.entity.run_explain_match")
    def test_server_explain_match_accepts_options(self, mock_run_explain_match):
        from entity_resolution.mcp import server

        mock_run_explain_match.return_value = {"ok": True}
        result = server.explain_match(
            collection="companies",
            key_a="a1",
            key_b="b1",
            options={"gating": {"require_token_overlap": True}},
        )
        assert result["ok"] is True
        kwargs = mock_run_explain_match.call_args.kwargs
        assert kwargs["options"]["gating"]["require_token_overlap"] is True

    @patch("entity_resolution.mcp.tools.entity.run_explain_match")
    def test_server_explain_match_surfaces_aliasing_diagnostics(self, mock_run_explain_match):
        from entity_resolution.mcp import server

        mock_run_explain_match.return_value = {
            "gates": {
                "aliasing": {
                    "managed_ref_requested": ["entity_aliases_v1"],
                    "managed_ref_applied": ["entity_aliases_v1"],
                    "managed_ref_missing": [],
                }
            }
        }
        result = server.explain_match(
            collection="companies",
            key_a="a1",
            key_b="b1",
            options={
                "aliasing": {
                    "sources": [{"type": "managed_ref", "ref": "entity_aliases_v1"}],
                    "managed_refs": {"entity_aliases_v1": {"ibm": ["international"]}},
                }
            },
        )

        aliasing = result["gates"]["aliasing"]
        assert aliasing["managed_ref_requested"] == ["entity_aliases_v1"]
        assert aliasing["managed_ref_applied"] == ["entity_aliases_v1"]
        assert aliasing["managed_ref_missing"] == []
        assert result["er_options_schema_version"] == "1.0"

    @patch("entity_resolution.mcp.tools.entity.run_explain_match")
    def test_server_explain_match_bubbles_alias_validation_errors(self, mock_run_explain_match):
        from entity_resolution.mcp import server

        mock_run_explain_match.side_effect = ValueError(
            "options.aliasing.sources must be an array/list when provided"
        )

        with pytest.raises(ValueError, match="options.aliasing.sources must be an array/list"):
            server.explain_match(
                collection="companies",
                key_a="a1",
                key_b="b1",
                options={"aliasing": {"sources": {"type": "managed_ref"}}},
            )

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_accepts_stages_options(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {"ok": True}
        server.find_duplicates(
            collection="companies",
            fields=["name"],
            options={
                "stages": [
                    {"type": "exact", "fields": ["name"], "min_score": 1.0},
                    {"type": "embedding", "fields": ["description"], "min_score": 0.78},
                ]
            },
        )

        req = mock_run_find_duplicates.call_args.kwargs["request"]
        assert len(req.stages) == 2
        assert req.stages[0]["type"] == "exact"
        assert req.stages[1]["type"] == "embedding"

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_accepts_gating_options(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {"ok": True}
        server.find_duplicates(
            collection="companies",
            fields=["name"],
            options={
                "gating": {
                    "min_margin": 0.06,
                    "mode": "shadow",
                    "require_token_overlap": True,
                    "token_overlap_bypass_score": 0.92,
                    "word_index_stopwords": ["llc"],
                    "token_type_affinity": {"bank": ["financial_institution"]},
                    "target_type_field": "type",
                }
            },
        )

        req = mock_run_find_duplicates.call_args.kwargs["request"]
        assert req.min_margin == 0.06
        assert req.gating_mode == "shadow"
        assert req.require_token_overlap is True
        assert req.token_overlap_bypass_score == 0.92
        assert req.word_index_stopwords == ["llc"]
        assert req.token_type_affinity == {"bank": ["financial_institution"]}
        assert req.target_type_field == "type"

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_accepts_aliasing_options(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {"ok": True}
        server.find_duplicates(
            collection="companies",
            fields=["name"],
            options={
                "aliasing": {
                    "sources": [
                        {"type": "inline", "map": {"co": ["company"]}},
                        {"type": "field", "field": "aliases"},
                    ]
                }
            },
        )

        req = mock_run_find_duplicates.call_args.kwargs["request"]
        assert len(req.alias_sources) == 2
        assert req.alias_sources[0]["type"] == "inline"
        assert req.alias_sources[1]["type"] == "field"

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_surfaces_aliasing_diagnostics(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {
            "similarity": {
                "gates": {
                    "aliasing": {
                        "managed_ref_requested": ["entity_aliases_v1"],
                        "managed_ref_applied": ["entity_aliases_v1"],
                        "managed_ref_missing": [],
                    }
                }
            }
        }
        result = server.find_duplicates(
            collection="companies",
            fields=["name"],
            options={
                "aliasing": {
                    "sources": [{"type": "managed_ref", "ref": "entity_aliases_v1"}],
                    "managed_refs": {"entity_aliases_v1": {"ibm": ["international"]}},
                }
            },
        )

        aliasing = result["similarity"]["gates"]["aliasing"]
        assert aliasing["managed_ref_requested"] == ["entity_aliases_v1"]
        assert aliasing["managed_ref_applied"] == ["entity_aliases_v1"]
        assert aliasing["managed_ref_missing"] == []
        assert result["er_options_schema_version"] == "1.0"

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_surfaces_multistage_gating_aliasing_diagnostics(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {
            "stages": {
                "enabled": True,
                "execution_mode": "multi_stage",
                "requested_stage_count": 2,
                "gating": {
                    "aliasing": {
                        "managed_ref_requested": ["missing_ref"],
                        "managed_ref_applied": [],
                        "managed_ref_missing": ["missing_ref"],
                    }
                },
                "stage_results": [],
            }
        }
        result = server.find_duplicates(
            collection="companies",
            fields=["name"],
            options={
                "stages": [
                    {"type": "bm25", "fields": ["name"], "min_score": 0.9},
                    {"type": "embedding", "fields": ["description"], "min_score": 0.78},
                ],
                "aliasing": {
                    "sources": [{"type": "managed_ref", "ref": "missing_ref"}],
                    "managed_refs": {},
                },
            },
        )

        aliasing = result["stages"]["gating"]["aliasing"]
        assert aliasing["managed_ref_requested"] == ["missing_ref"]
        assert aliasing["managed_ref_applied"] == []
        assert aliasing["managed_ref_missing"] == ["missing_ref"]
        assert result["er_options_schema_version"] == "1.0"

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_surfaces_single_stage_gating_aliasing_diagnostics(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {
            "stages": {
                "enabled": True,
                "execution_mode": "single_stage_scaffold",
                "requested_stage_count": 1,
                "gating": {
                    "aliasing": {
                        "managed_ref_requested": ["missing_ref"],
                        "managed_ref_applied": [],
                        "managed_ref_missing": ["missing_ref"],
                    }
                },
            }
        }
        result = server.find_duplicates(
            collection="companies",
            fields=["name"],
            options={
                "stages": [{"type": "exact", "fields": ["name"], "min_score": 0.8}],
                "aliasing": {
                    "sources": [{"type": "managed_ref", "ref": "missing_ref"}],
                    "managed_refs": {},
                },
            },
        )

        aliasing = result["stages"]["gating"]["aliasing"]
        assert aliasing["managed_ref_requested"] == ["missing_ref"]
        assert aliasing["managed_ref_applied"] == []
        assert aliasing["managed_ref_missing"] == ["missing_ref"]
        assert result["er_options_schema_version"] == "1.0"

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_accepts_token_jaccard_similarity_options(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {"ok": True}
        server.find_duplicates(
            collection="companies",
            fields=["name"],
            options={
                "similarity": {
                    "type": "token_jaccard",
                    "token_jaccard_fields": ["name", "aliases"],
                    "token_jaccard_min_score": 0.61,
                }
            },
        )

        req = mock_run_find_duplicates.call_args.kwargs["request"]
        assert req.similarity_type == "token_jaccard"
        assert req.token_jaccard_fields == ["name", "aliases"]
        assert req.token_jaccard_min_score == 0.61

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_surfaces_deprecation_warnings(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {"ok": True}
        result = server.find_duplicates(
            collection="companies",
            fields=["name"],
            strategy="exact",
            options={"blocking": {"strategy": "bm25"}},
        )
        assert result["ok"] is True
        assert "deprecation_warnings" in result
        assert len(result["deprecation_warnings"]) >= 1
        assert result["er_options_schema_version"] == "1.0"

    @patch("entity_resolution.mcp.tools.entity.run_resolve_entity_request")
    def test_server_resolve_entity_options_override_legacy(self, mock_run_resolve_entity):
        from entity_resolution.mcp import server

        mock_run_resolve_entity.return_value = [{"candidate_key": "c1", "score": 0.91}]
        server.resolve_entity(
            collection="companies",
            record={"name": "Acme"},
            fields=["name"],
            confidence_threshold=0.7,
            top_k=10,
            options={
                "retrieval": {"fields": ["name", "aliases"], "top_k": 3},
                "similarity": {"confidence_threshold": 0.88},
            },
        )

        kwargs = mock_run_resolve_entity.call_args.kwargs
        req = kwargs["request"]
        assert req.collection == "companies"
        assert req.fields == ["name", "aliases"]
        assert req.confidence_threshold == 0.88
        assert req.top_k == 3

    @patch("entity_resolution.mcp.tools.pipeline.run_find_duplicates_request")
    def test_server_find_duplicates_legacy_and_options_equivalent(self, mock_run_find_duplicates):
        from entity_resolution.mcp import server

        mock_run_find_duplicates.return_value = {"ok": True}

        server.find_duplicates(
            collection="companies",
            fields=["name", "city"],
            strategy="bm25",
            confidence_threshold=0.9,
            max_block_size=120,
            store_clusters=False,
        )
        req_legacy = mock_run_find_duplicates.call_args.kwargs["request"]

        server.find_duplicates(
            collection="companies",
            fields=["name", "city"],
            options={
                "blocking": {"strategy": "bm25", "fields": ["name", "city"], "max_block_size": 120},
                "similarity": {"confidence_threshold": 0.9},
                "clustering": {"store_clusters": False},
            },
        )
        req_options = mock_run_find_duplicates.call_args.kwargs["request"]

        assert req_legacy.collection == req_options.collection
        assert req_legacy.fields == req_options.fields
        assert req_legacy.strategy == req_options.strategy
        assert req_legacy.confidence_threshold == req_options.confidence_threshold
        assert req_legacy.max_block_size == req_options.max_block_size
        assert req_legacy.store_clusters == req_options.store_clusters

    @patch("entity_resolution.mcp.tools.entity.run_resolve_entity_request")
    def test_server_resolve_entity_legacy_and_options_equivalent(self, mock_run_resolve_entity):
        from entity_resolution.mcp import server

        mock_run_resolve_entity.return_value = []

        server.resolve_entity(
            collection="companies",
            record={"name": "Acme"},
            fields=["name"],
            confidence_threshold=0.8,
            top_k=5,
        )
        req_legacy = mock_run_resolve_entity.call_args.kwargs["request"]

        server.resolve_entity(
            collection="companies",
            record={"name": "Acme"},
            fields=["name"],
            options={
                "retrieval": {"fields": ["name"], "top_k": 5},
                "similarity": {"confidence_threshold": 0.8},
            },
        )
        req_options = mock_run_resolve_entity.call_args.kwargs["request"]

        assert req_legacy.collection == req_options.collection
        assert req_legacy.record == req_options.record
        assert req_legacy.fields == req_options.fields
        assert req_legacy.confidence_threshold == req_options.confidence_threshold
        assert req_legacy.top_k == req_options.top_k

    @patch("entity_resolution.mcp.tools.entity.run_resolve_entity_request")
    def test_server_resolve_entity_default_response_is_list(self, mock_run_resolve_entity):
        from entity_resolution.mcp import server

        mock_run_resolve_entity.return_value = [{"candidate_key": "c1", "score": 0.91}]
        result = server.resolve_entity(
            collection="companies",
            record={"name": "Acme"},
            fields=["name"],
        )
        assert isinstance(result, list)
        assert result[0]["candidate_key"] == "c1"

    @patch("entity_resolution.mcp.tools.entity.run_resolve_entity_request")
    def test_server_resolve_entity_can_return_envelope(self, mock_run_resolve_entity):
        from entity_resolution.mcp import server

        mock_run_resolve_entity.return_value = [{"candidate_key": "c1", "score": 0.91}]
        result = server.resolve_entity(
            collection="companies",
            record={"name": "Acme"},
            fields=["name"],
            confidence_threshold=0.7,
            options={
                "retrieval": {"fields": ["name", "aliases"]},
                "similarity": {"confidence_threshold": 0.88},
                "diagnostics": {"response_envelope": True},
            },
        )

        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["response_format"] == "envelope-v1"
        assert isinstance(result["result"], list)
        assert "deprecation_warnings" in result

    @patch("entity_resolution.mcp.tools.cluster.run_list_collections")
    def test_server_list_collections_default_response_is_list(self, mock_run):
        from entity_resolution.mcp import server

        mock_run.return_value = [{"name": "companies", "type": "document", "count": 42}]
        result = server.list_collections()
        assert isinstance(result, list)
        assert result[0]["name"] == "companies"

    @patch("entity_resolution.mcp.tools.cluster.run_list_collections")
    def test_server_list_collections_can_return_envelope(self, mock_run):
        from entity_resolution.mcp import server

        mock_run.return_value = [{"name": "companies", "type": "document", "count": 42}]
        result = server.list_collections(
            options={"diagnostics": {"response_envelope": True}},
        )

        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["response_format"] == "envelope-v1"
        assert result["er_options_schema_version"] == "1.0"
        assert isinstance(result["result"], list)
        assert result["result"][0]["name"] == "companies"

    @patch("entity_resolution.mcp.tools.cluster.run_get_clusters")
    def test_server_get_clusters_default_response_is_list(self, mock_run):
        from entity_resolution.mcp import server

        mock_run.return_value = [{"cluster_id": "c1", "members": ["a", "b"], "size": 2}]
        result = server.get_clusters(collection="companies")
        assert isinstance(result, list)
        assert result[0]["cluster_id"] == "c1"

    @patch("entity_resolution.mcp.tools.cluster.run_get_clusters")
    def test_server_get_clusters_can_return_envelope(self, mock_run):
        from entity_resolution.mcp import server

        mock_run.return_value = [{"cluster_id": "c1", "members": ["a", "b"], "size": 2}]
        result = server.get_clusters(
            collection="companies",
            options={"diagnostics": {"response_envelope": True}},
        )

        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["response_format"] == "envelope-v1"
        assert isinstance(result["result"], list)
        assert result["result"][0]["cluster_id"] == "c1"

    @patch("entity_resolution.mcp.tools.entity.run_resolve_cross_collection_request")
    def test_server_resolve_entity_cross_collection_forwards_request(self, mock_run):
        from entity_resolution.mcp import server

        mock_run.return_value = {"stats": {"edges_created": 5}}
        result = server.resolve_entity_cross_collection(
            source_collection="registrations",
            target_collection="companies",
            source_fields=["company_name"],
            target_fields=["legal_name"],
            options={"retrieval": {"candidate_limit": 100}},
        )

        assert result["stats"]["edges_created"] == 5
        req = mock_run.call_args.kwargs["request"]
        assert req.source_collection == "registrations"
        assert req.target_collection == "companies"
        assert req.source_fields == {"company_name": "company_name"}
        assert req.target_fields == {"company_name": "legal_name"}
        assert req.candidate_limit == 100

    @patch("entity_resolution.mcp.tools.entity.run_resolve_cross_collection_request")
    def test_server_cross_collection_field_mapping_surfaces_deprecation(self, mock_run):
        from entity_resolution.mcp import server

        mock_run.return_value = {"stats": {"edges_created": 0}}
        result = server.resolve_entity_cross_collection(
            source_collection="regs",
            target_collection="duns",
            source_fields=["name"],
            target_fields=["legal_name"],
            options={
                "retrieval": {
                    "field_mapping": {
                        "company": {"source": "BR_Name", "target": "DUNS_NAME"},
                    }
                }
            },
        )

        assert "deprecation_warnings" in result
        assert any("field_mapping" in w for w in result["deprecation_warnings"])
        req = mock_run.call_args.kwargs["request"]
        assert req.source_fields == {"company": "BR_Name"}
        assert req.target_fields == {"company": "DUNS_NAME"}
