"""
Unit tests for entity_resolution.reasoning.feedback module.

Covers FeedbackStore (save, retrieve, stats) and ThresholdOptimizer
(defaults, percentile fallback, insufficient-sample path).
All ArangoDB interactions are mocked.
"""

import hashlib
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from entity_resolution.reasoning.feedback import (
    FeedbackStore,
    ThresholdOptimizer,
    _content_hash,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Provide a mock ArangoDB database that tracks collection operations."""
    db = MagicMock()
    mock_col = MagicMock()
    db.has_collection.return_value = True
    db.collection.return_value = mock_col
    db.create_collection.return_value = mock_col
    return db


@pytest.fixture
def store(mock_db):
    """Provide a FeedbackStore backed by the mock database."""
    return FeedbackStore(mock_db, collection="er_test_feedback")


# ---------------------------------------------------------------------------
# _content_hash helper
# ---------------------------------------------------------------------------

class TestContentHash:
    """Tests for the module-level _content_hash helper."""

    @pytest.mark.unit
    def test_deterministic(self):
        """Same record produces the same hash."""
        rec = {"name": "Acme", "city": "Boston"}
        assert _content_hash(rec) == _content_hash(rec)

    @pytest.mark.unit
    def test_ignores_underscore_keys(self):
        """Keys starting with underscore (_key, _id, _rev) are excluded."""
        rec_a = {"name": "Acme", "_key": "123"}
        rec_b = {"name": "Acme", "_key": "999"}
        assert _content_hash(rec_a) == _content_hash(rec_b)

    @pytest.mark.unit
    def test_different_records_differ(self):
        """Different content produces different hashes."""
        assert _content_hash({"a": 1}) != _content_hash({"a": 2})


# ---------------------------------------------------------------------------
# FeedbackStore
# ---------------------------------------------------------------------------

class TestFeedbackStore:
    """Tests for FeedbackStore."""

    @pytest.mark.unit
    def test_creates_collection_when_missing(self, mock_db):
        """If the collection doesn't exist, it is created."""
        mock_db.has_collection.return_value = False
        FeedbackStore(mock_db, collection="new_col")
        mock_db.create_collection.assert_called_once_with("new_col")

    @pytest.mark.unit
    def test_skips_creation_when_exists(self, mock_db):
        """If the collection already exists, create_collection is not called."""
        mock_db.has_collection.return_value = True
        FeedbackStore(mock_db, collection="existing")
        mock_db.create_collection.assert_not_called()

    @pytest.mark.unit
    def test_save_inserts_document(self, store, mock_db):
        """save() calls insert with overwrite=True."""
        rec_a = {"_key": "k1", "name": "Alice"}
        rec_b = {"_key": "k2", "name": "Bob"}

        key = store.save(rec_a, rec_b, score=0.85, decision="match", confidence=0.9)

        mock_db.collection.return_value.insert.assert_called_once()
        call_args = mock_db.collection.return_value.insert.call_args
        doc = call_args[0][0]

        assert doc["_key"] == key
        assert doc["decision"] == "match"
        assert doc["score"] == 0.85
        assert doc["confidence"] == 0.9
        assert doc["source"] == "llm"
        assert call_args[1]["overwrite"] is True

    @pytest.mark.unit
    def test_save_deterministic_key(self, store):
        """Same pair always produces the same document key."""
        rec_a = {"_key": "k1"}
        rec_b = {"_key": "k2"}
        key1 = store.save(rec_a, rec_b, 0.5, "no_match", 0.7)
        key2 = store.save(rec_a, rec_b, 0.6, "match", 0.8)
        assert key1 == key2

    @pytest.mark.unit
    def test_save_symmetric_key(self, store):
        """Order of records doesn't affect the document key."""
        rec_a = {"_key": "alpha"}
        rec_b = {"_key": "beta"}
        key_ab = store.save(rec_a, rec_b, 0.5, "match", 0.9)
        key_ba = store.save(rec_b, rec_a, 0.5, "match", 0.9)
        assert key_ab == key_ba

    @pytest.mark.unit
    def test_save_uses_content_hash_when_no_key(self, store):
        """Records without _key get a content hash as identifier."""
        rec_a = {"name": "Foo"}
        rec_b = {"name": "Bar"}
        key = store.save(rec_a, rec_b, 0.6, "match", 0.8)
        assert isinstance(key, str) and len(key) == 32  # md5 hexdigest

    @pytest.mark.unit
    def test_record_human_correction(self, store, mock_db):
        """record_human_correction delegates to save with source='human'."""
        store.record_human_correction("k1", "k2", "no_match")

        call_args = mock_db.collection.return_value.insert.call_args
        doc = call_args[0][0]
        assert doc["source"] == "human"
        assert doc["decision"] == "no_match"
        assert doc["confidence"] == 1.0

    @pytest.mark.unit
    def test_all_verdicts(self, store, mock_db):
        """all_verdicts returns the full cursor as a list."""
        mock_db.aql.execute.return_value = iter([
            {"decision": "match", "score": 0.9},
            {"decision": "no_match", "score": 0.3},
        ])
        result = store.all_verdicts()
        assert len(result) == 2
        mock_db.aql.execute.assert_called_once()

    @pytest.mark.unit
    def test_verdicts_by_decision(self, store, mock_db):
        """verdicts_by_decision passes the correct AQL filter."""
        mock_db.aql.execute.return_value = iter([])
        store.verdicts_by_decision("match")

        call_args = mock_db.aql.execute.call_args
        assert call_args[1]["bind_vars"]["d"] == "match"

    @pytest.mark.unit
    def test_stats(self, store, mock_db):
        """stats() returns aggregated data from AQL plus a total count."""
        mock_db.aql.execute.return_value = iter([
            {"decision": "match", "count": 5, "avg_score": 0.8, "avg_confidence": 0.9},
        ])
        mock_db.collection.return_value.count.return_value = 10

        result = store.stats()
        assert "by_decision" in result
        assert result["total"] == 10


# ---------------------------------------------------------------------------
# ThresholdOptimizer
# ---------------------------------------------------------------------------

class TestThresholdOptimizer:
    """Tests for ThresholdOptimizer."""

    @pytest.mark.unit
    def test_returns_defaults_when_insufficient_samples(self, store, mock_db):
        """With fewer samples than min_samples, default thresholds are returned."""
        mock_db.aql.execute.return_value = iter([
            {"score": 0.7, "decision": "match"},
        ])
        optimizer = ThresholdOptimizer(store, min_samples=20)
        result = optimizer.optimize()

        assert result["optimized"] is False
        assert result["low_threshold"] == 0.55
        assert result["high_threshold"] == 0.80
        assert result["sample_count"] == 1

    @pytest.mark.unit
    def test_returns_defaults_with_zero_samples(self, store, mock_db):
        """With no samples at all, defaults are returned."""
        mock_db.aql.execute.return_value = iter([])
        optimizer = ThresholdOptimizer(store, min_samples=5)
        result = optimizer.optimize()

        assert result["optimized"] is False
        assert result["sample_count"] == 0

    @pytest.mark.unit
    def test_percentile_fallback_with_enough_samples(self, store, mock_db):
        """When sklearn is unavailable, percentile method is used."""
        verdicts = [
            {"score": 0.3 + i * 0.02, "decision": "no_match"} for i in range(15)
        ] + [
            {"score": 0.7 + i * 0.01, "decision": "match"} for i in range(15)
        ]
        mock_db.aql.execute.return_value = iter(verdicts)

        optimizer = ThresholdOptimizer(store, min_samples=20)

        with patch.dict("sys.modules", {"sklearn": None, "sklearn.isotonic": None}):
            result = optimizer._optimize_percentile(
                [v["score"] for v in verdicts],
                [1 if v["decision"] == "match" else 0 for v in verdicts],
                len(verdicts),
            )

        assert result["optimized"] is True
        assert result["method"] == "percentile"
        assert 0 < result["low_threshold"] < result["high_threshold"] <= 0.95

    @pytest.mark.unit
    def test_percentile_returns_defaults_without_positives(self, store):
        """Percentile method returns defaults when all verdicts are no_match."""
        optimizer = ThresholdOptimizer(store, min_samples=2)
        result = optimizer._optimize_percentile(
            scores=[0.3, 0.4, 0.5],
            labels=[0, 0, 0],
            n=3,
        )
        assert result["optimized"] is False
        assert "Not enough positive and negative examples" in result["reason"]

    @pytest.mark.unit
    def test_percentile_returns_defaults_without_negatives(self, store):
        """Percentile method returns defaults when all verdicts are match."""
        optimizer = ThresholdOptimizer(store, min_samples=2)
        result = optimizer._optimize_percentile(
            scores=[0.7, 0.8, 0.9],
            labels=[1, 1, 1],
            n=3,
        )
        assert result["optimized"] is False

    @pytest.mark.unit
    def test_optimize_respects_custom_target_precision(self, store, mock_db):
        """Custom target_precision is stored and accessible."""
        optimizer = ThresholdOptimizer(store, target_precision=0.90, min_samples=5)
        assert optimizer.target_precision == 0.90

    @pytest.mark.unit
    def test_percentile_thresholds_bounded(self, store):
        """Percentile high_threshold is capped at 0.95."""
        optimizer = ThresholdOptimizer(store, min_samples=2)
        result = optimizer._optimize_percentile(
            scores=[0.50, 0.55, 0.60, 0.65, 0.70, 0.75,
                    0.10, 0.15, 0.20, 0.25, 0.30, 0.35],
            labels=[1, 1, 1, 1, 1, 1,
                    0, 0, 0, 0, 0, 0],
            n=12,
        )
        assert result["high_threshold"] <= 0.95
        assert result["high_threshold"] >= result["low_threshold"] + 0.10
