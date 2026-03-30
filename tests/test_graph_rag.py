"""Tests for GraphRAG document entity extraction and linking."""

import json
import pytest
from unittest.mock import MagicMock, patch

from entity_resolution.reasoning.graph_rag import (
    DocumentEntityExtractor,
    GraphRAGLinker,
)


class TestDocumentEntityExtractor:
    def test_parse_response_valid_json_array(self):
        raw = '[{"name": "Acme", "type": "company", "attributes": {}}]'
        result = DocumentEntityExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["name"] == "Acme"

    def test_parse_response_markdown_fenced(self):
        raw = '```json\n[{"name": "Test"}]\n```'
        result = DocumentEntityExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["name"] == "Test"

    def test_parse_response_invalid_json(self):
        raw = "This is not JSON at all"
        result = DocumentEntityExtractor._parse_response(raw)
        assert result == []

    def test_parse_response_single_object(self):
        raw = '{"name": "Solo", "type": "person"}'
        result = DocumentEntityExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["type"] == "person"


class TestGraphRAGLinker:
    def _make_db(self, entities):
        db = MagicMock()
        cursor = iter(entities)
        db.aql.execute.return_value = cursor
        db.has_collection.return_value = True
        col = MagicMock()
        col.insert.return_value = {"_key": "edge_123"}
        db.collection.return_value = col
        return db

    def test_link_matches_above_threshold(self):
        db = self._make_db([
            {"key": "c1", "name": "Acme Corporation"},
            {"key": "c2", "name": "Globex Industries"},
        ])
        linker = GraphRAGLinker(
            db=db,
            entity_collection="companies",
            edge_collection="extraction_links",
            similarity_threshold=0.70,
        )
        extracted = [{"name": "Acme Corp", "type": "company"}]
        results = linker.link(extracted)
        assert len(results) == 1
        assert results[0]["linked"] is True
        assert results[0]["matched_key"] == "c1"
        assert results[0]["score"] > 0.70

    def test_link_no_match_below_threshold(self):
        db = self._make_db([
            {"key": "c1", "name": "Totally Different Company"},
        ])
        linker = GraphRAGLinker(
            db=db,
            entity_collection="companies",
            edge_collection="links",
            similarity_threshold=0.95,
        )
        extracted = [{"name": "Acme Corp", "type": "company"}]
        results = linker.link(extracted)
        assert len(results) == 1
        assert results[0]["linked"] is False
        assert results[0]["matched_key"] is None

    def test_link_empty_name_skipped(self):
        db = self._make_db([])
        linker = GraphRAGLinker(db=db, entity_collection="c", edge_collection="e")
        results = linker.link([{"name": "", "type": "company"}])
        assert len(results) == 1
        assert results[0]["linked"] is False

    def test_link_with_source_doc_key(self):
        db = self._make_db([{"key": "c1", "name": "Acme Corporation"}])
        linker = GraphRAGLinker(db=db, entity_collection="c", edge_collection="e")
        results = linker.link(
            [{"name": "Acme Corp", "type": "company"}],
            source_doc_key="doc_42",
        )
        assert results[0]["linked"] is True
        assert results[0]["edge_key"] == "edge_123"
