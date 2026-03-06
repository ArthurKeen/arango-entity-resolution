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
        assert result == {"ok": True}


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
