"""
Unit tests for entity_resolution.strategies.geographic_blocking module.

Tests GeographicBlockingStrategy initialisation, configuration validation,
AQL query generation, and helper methods.  All ArangoDB access is mocked.
"""

import pytest
from unittest.mock import MagicMock

from entity_resolution.strategies.geographic_blocking import (
    GeographicBlockingStrategy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Mock ArangoDB database."""
    mock_db = MagicMock()
    mock_db.aql.execute.return_value = iter([])
    return mock_db


# ---------------------------------------------------------------------------
# Initialization & configuration validation
# ---------------------------------------------------------------------------

class TestGeographicBlockingInit:
    """Tests for __init__ and _validate_configuration."""

    @pytest.mark.unit
    def test_valid_state_blocking(self, db):
        """State blocking initialises successfully with correct fields."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "primary_state"},
        )
        assert strategy.blocking_type == "state"
        assert strategy.geographic_fields == {"state": "primary_state"}

    @pytest.mark.unit
    def test_valid_city_state_blocking(self, db):
        """city_state blocking requires both city and state fields."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="city_state",
            geographic_fields={"city": "primary_city", "state": "primary_state"},
        )
        assert strategy.blocking_type == "city_state"

    @pytest.mark.unit
    def test_valid_zip_range_blocking(self, db):
        """zip_range blocking accepts zip_ranges parameter."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="zip_range",
            geographic_fields={"zip": "postal_code"},
            zip_ranges=[("570", "577")],
        )
        assert strategy.zip_ranges == [("570", "577")]

    @pytest.mark.unit
    def test_rejects_invalid_blocking_type(self, db):
        """An unsupported blocking_type raises ValueError."""
        with pytest.raises(ValueError, match="must be one of"):
            GeographicBlockingStrategy(
                db=db,
                collection="companies",
                blocking_type="invalid_type",
                geographic_fields={"state": "primary_state"},
            )

    @pytest.mark.unit
    def test_rejects_missing_required_field(self, db):
        """city_state blocking without 'state' field raises ValueError."""
        with pytest.raises(ValueError, match="Missing"):
            GeographicBlockingStrategy(
                db=db,
                collection="companies",
                blocking_type="city_state",
                geographic_fields={"city": "primary_city"},
            )

    @pytest.mark.unit
    def test_rejects_zip_range_without_ranges(self, db):
        """zip_range blocking without zip_ranges raises ValueError."""
        with pytest.raises(ValueError, match="requires zip_ranges"):
            GeographicBlockingStrategy(
                db=db,
                collection="companies",
                blocking_type="zip_range",
                geographic_fields={"zip": "postal_code"},
                zip_ranges=[],
            )

    @pytest.mark.unit
    def test_default_block_sizes(self, db):
        """Default min/max block sizes are applied."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "st"},
        )
        assert strategy.min_block_size == 2
        assert strategy.max_block_size == 1000

    @pytest.mark.unit
    def test_custom_block_sizes(self, db):
        """Custom min/max block sizes are stored."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="city",
            geographic_fields={"city": "city_name"},
            max_block_size=500,
            min_block_size=5,
        )
        assert strategy.max_block_size == 500
        assert strategy.min_block_size == 5


# ---------------------------------------------------------------------------
# AQL query generation
# ---------------------------------------------------------------------------

class TestGeographicBlockingQuery:
    """Tests for _build_geographic_query and its helpers."""

    @pytest.mark.unit
    def test_state_query_contains_collect(self, db):
        """State blocking query COLLECTs on the state field."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "primary_state"},
        )
        query = strategy._build_geographic_query()
        assert "COLLECT state = d.primary_state" in query
        assert "FOR d IN companies" in query

    @pytest.mark.unit
    def test_city_state_query_collects_both(self, db):
        """city_state blocking COLLECTs on both city and state."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="city_state",
            geographic_fields={"city": "name_city", "state": "name_state"},
        )
        query = strategy._build_geographic_query()
        assert "city = d.name_city" in query
        assert "state = d.name_state" in query

    @pytest.mark.unit
    def test_zip_range_query_has_substring_filter(self, db):
        """zip_range blocking generates SUBSTRING-based range filters."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="zip_range",
            geographic_fields={"zip": "postal_code"},
            zip_ranges=[("570", "577")],
        )
        query = strategy._build_geographic_query()
        assert "SUBSTRING" in query
        assert '"570"' in query
        assert '"577"' in query

    @pytest.mark.unit
    def test_zip_prefix_query(self, db):
        """zip_prefix blocking collects on first 3 digits."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="zip_prefix",
            geographic_fields={"zip": "zip_code"},
        )
        query = strategy._build_geographic_query()
        assert "SUBSTRING(TO_STRING(d.zip_code), 0, 3)" in query

    @pytest.mark.unit
    def test_block_size_filters_in_query(self, db):
        """Query filters out blocks outside min/max range."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="city",
            geographic_fields={"city": "city_name"},
            min_block_size=3,
            max_block_size=50,
        )
        query = strategy._build_geographic_query()
        assert "LENGTH(doc_keys) >= 3" in query
        assert "LENGTH(doc_keys) <= 50" in query

    @pytest.mark.unit
    def test_filters_added_to_query(self, db):
        """Field-level filters appear as FILTER clauses."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "primary_state"},
            filters={"primary_state": {"not_null": True}},
        )
        query = strategy._build_geographic_query()
        assert "d.primary_state != null" in query


# ---------------------------------------------------------------------------
# generate_candidates
# ---------------------------------------------------------------------------

class TestGeographicBlockingGenerateCandidates:
    """Tests for generate_candidates with mocked AQL results."""

    @pytest.mark.unit
    def test_returns_empty_for_no_results(self, db):
        """With no AQL results, returns an empty list."""
        db.aql.execute.return_value = iter([])
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "st"},
        )
        result = strategy.generate_candidates()
        assert result == []

    @pytest.mark.unit
    def test_normalises_returned_pairs(self, db):
        """Pairs returned by AQL are normalised (doc1_key < doc2_key)."""
        db.aql.execute.return_value = iter([
            {"doc1_key": "z", "doc2_key": "a", "blocking_keys": {"state": "SD"},
             "block_size": 5, "method": "geographic_blocking", "blocking_type": "state"},
        ])
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "st"},
        )
        result = strategy.generate_candidates()
        assert len(result) == 1
        assert result[0]["doc1_key"] < result[0]["doc2_key"]

    @pytest.mark.unit
    def test_statistics_updated(self, db):
        """After generate_candidates, statistics contain expected keys."""
        db.aql.execute.return_value = iter([
            {"doc1_key": "a", "doc2_key": "b", "blocking_keys": {"state": "SD"},
             "block_size": 5, "method": "geographic_blocking", "blocking_type": "state"},
        ])
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "st"},
        )
        strategy.generate_candidates()
        stats = strategy.get_statistics()

        assert stats["total_pairs"] == 1
        assert stats["blocking_type"] == "state"
        assert "execution_time_seconds" in stats


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------

class TestGeographicBlockingHelpers:
    """Tests for private helper methods."""

    @pytest.mark.unit
    def test_estimate_blocks_processed_empty(self, db):
        """No pairs means zero blocks."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "st"},
        )
        assert strategy._estimate_blocks_processed([]) == 0

    @pytest.mark.unit
    def test_estimate_blocks_processed_distinct(self, db):
        """Two distinct blocking key sets count as two blocks."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="state",
            geographic_fields={"state": "st"},
        )
        pairs = [
            {"blocking_keys": {"state": "SD"}},
            {"blocking_keys": {"state": "SD"}},
            {"blocking_keys": {"state": "MN"}},
        ]
        assert strategy._estimate_blocks_processed(pairs) == 2

    @pytest.mark.unit
    def test_repr(self, db):
        """__repr__ contains strategy name, collection, and block sizes."""
        strategy = GeographicBlockingStrategy(
            db=db,
            collection="companies",
            blocking_type="city",
            geographic_fields={"city": "city_name"},
            min_block_size=2,
            max_block_size=500,
        )
        r = repr(strategy)
        assert "GeographicBlockingStrategy" in r
        assert "companies" in r
        assert "city" in r
