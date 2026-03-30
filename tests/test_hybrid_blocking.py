"""
Unit tests for entity_resolution.strategies.hybrid_blocking module.

Tests HybridBlockingStrategy initialisation, parameter validation,
AQL query generation, weight normalisation, and score averaging.
All ArangoDB access is mocked.
"""

import pytest
from unittest.mock import MagicMock

from entity_resolution.strategies.hybrid_blocking import (
    HybridBlockingStrategy,
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


def _make_strategy(db, **overrides):
    """Helper to build a HybridBlockingStrategy with sensible defaults."""
    defaults = dict(
        db=db,
        collection="companies",
        search_view="companies_search",
        search_fields={"name": 0.6, "address": 0.4},
        levenshtein_threshold=0.85,
        bm25_threshold=2.0,
        bm25_weight=0.2,
        limit_per_entity=20,
    )
    defaults.update(overrides)
    return HybridBlockingStrategy(**defaults)


# ---------------------------------------------------------------------------
# Initialization & parameter validation
# ---------------------------------------------------------------------------

class TestHybridBlockingInit:
    """Tests for __init__ parameter validation."""

    @pytest.mark.unit
    def test_valid_initialization(self, db):
        """Strategy initialises with valid parameters."""
        strategy = _make_strategy(db)
        assert strategy.collection == "companies"
        assert strategy.search_view == "companies_search"
        assert strategy.levenshtein_threshold == 0.85
        assert strategy.bm25_threshold == 2.0
        assert strategy.bm25_weight == 0.2
        assert strategy.levenshtein_weight == pytest.approx(0.8)
        assert strategy.limit_per_entity == 20
        assert strategy.blocking_field is None

    @pytest.mark.unit
    def test_rejects_empty_search_view(self, db):
        """Empty search_view raises ValueError."""
        with pytest.raises(ValueError, match="search_view cannot be empty"):
            _make_strategy(db, search_view="")

    @pytest.mark.unit
    def test_rejects_empty_search_fields(self, db):
        """Empty search_fields raises ValueError."""
        with pytest.raises(ValueError, match="search_fields cannot be empty"):
            _make_strategy(db, search_fields={})

    @pytest.mark.unit
    def test_rejects_levenshtein_threshold_below_zero(self, db):
        """levenshtein_threshold < 0 raises ValueError."""
        with pytest.raises(ValueError, match="levenshtein_threshold must be between"):
            _make_strategy(db, levenshtein_threshold=-0.1)

    @pytest.mark.unit
    def test_rejects_levenshtein_threshold_above_one(self, db):
        """levenshtein_threshold > 1 raises ValueError."""
        with pytest.raises(ValueError, match="levenshtein_threshold must be between"):
            _make_strategy(db, levenshtein_threshold=1.5)

    @pytest.mark.unit
    def test_rejects_non_positive_bm25_threshold(self, db):
        """bm25_threshold <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="bm25_threshold must be positive"):
            _make_strategy(db, bm25_threshold=0)

    @pytest.mark.unit
    def test_rejects_bm25_weight_out_of_range(self, db):
        """bm25_weight outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="bm25_weight must be between"):
            _make_strategy(db, bm25_weight=1.5)

    @pytest.mark.unit
    def test_rejects_non_positive_limit_per_entity(self, db):
        """limit_per_entity <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="limit_per_entity must be positive"):
            _make_strategy(db, limit_per_entity=0)

    @pytest.mark.unit
    def test_blocking_field_stored(self, db):
        """Optional blocking_field is validated and stored."""
        strategy = _make_strategy(db, blocking_field="state")
        assert strategy.blocking_field == "state"


# ---------------------------------------------------------------------------
# Weight normalisation
# ---------------------------------------------------------------------------

class TestWeightNormalization:
    """Tests for _normalize_weights."""

    @pytest.mark.unit
    def test_weights_normalised_to_one(self, db):
        """Field weights sum to 1.0 after normalisation."""
        strategy = _make_strategy(db, search_fields={"name": 3, "address": 7})
        total = sum(strategy.search_fields.values())
        assert total == pytest.approx(1.0)
        assert strategy.search_fields["name"] == pytest.approx(0.3)
        assert strategy.search_fields["address"] == pytest.approx(0.7)

    @pytest.mark.unit
    def test_single_field_gets_weight_one(self, db):
        """A single field is normalised to weight 1.0."""
        strategy = _make_strategy(db, search_fields={"name": 5.0})
        assert strategy.search_fields["name"] == pytest.approx(1.0)

    @pytest.mark.unit
    def test_rejects_all_zero_weights(self, db):
        """All-zero weights raise ValueError."""
        with pytest.raises(ValueError, match="cannot all be zero"):
            _make_strategy(db, search_fields={"name": 0, "address": 0})


# ---------------------------------------------------------------------------
# AQL query generation
# ---------------------------------------------------------------------------

class TestHybridBlockingQuery:
    """Tests for _build_hybrid_query."""

    @pytest.mark.unit
    def test_query_uses_collection_and_view(self, db):
        """Generated AQL references the source collection and search view."""
        strategy = _make_strategy(db)
        query = strategy._build_hybrid_query()
        assert "FOR d1 IN companies" in query
        assert "FOR d2 IN companies_search" in query

    @pytest.mark.unit
    def test_query_contains_bm25(self, db):
        """Query computes BM25 score and filters by threshold."""
        strategy = _make_strategy(db)
        query = strategy._build_hybrid_query()
        assert "LET bm25_score = BM25(d2)" in query
        assert "FILTER bm25_score > @bm25_threshold" in query

    @pytest.mark.unit
    def test_query_contains_levenshtein(self, db):
        """Query computes Levenshtein distance for search fields."""
        strategy = _make_strategy(db)
        query = strategy._build_hybrid_query()
        assert "LEVENSHTEIN_DISTANCE" in query
        assert "FILTER levenshtein_score >= @levenshtein_threshold" in query

    @pytest.mark.unit
    def test_query_prevents_self_match(self, db):
        """Query ensures a document is not matched with itself."""
        strategy = _make_strategy(db)
        query = strategy._build_hybrid_query()
        assert "FILTER d1._key < d2._key" in query

    @pytest.mark.unit
    def test_query_has_limit(self, db):
        """Query limits candidates per entity."""
        strategy = _make_strategy(db)
        query = strategy._build_hybrid_query()
        assert "LIMIT @limit_per_entity" in query

    @pytest.mark.unit
    def test_blocking_field_adds_filter(self, db):
        """When blocking_field is set, an equality filter appears in the query."""
        strategy = _make_strategy(db, blocking_field="state")
        query = strategy._build_hybrid_query()
        assert "d2.state == d1.state" in query

    @pytest.mark.unit
    def test_query_with_field_filters(self, db):
        """Field-level not_null / min_length filters appear in the query."""
        strategy = _make_strategy(
            db,
            filters={
                "name": {"not_null": True, "min_length": 3},
            },
        )
        query = strategy._build_hybrid_query()
        assert "d1.name != null" in query
        assert "LENGTH(d1.name) > 3" in query


# ---------------------------------------------------------------------------
# Score averaging
# ---------------------------------------------------------------------------

class TestCalculateAvgScore:
    """Tests for _calculate_avg_score."""

    @pytest.mark.unit
    def test_average_of_scores(self, db):
        """Average is correctly computed from pair scores."""
        strategy = _make_strategy(db)
        pairs = [
            {"levenshtein_score": 0.8},
            {"levenshtein_score": 0.9},
            {"levenshtein_score": 1.0},
        ]
        assert strategy._calculate_avg_score(pairs, "levenshtein_score") == pytest.approx(0.9)

    @pytest.mark.unit
    def test_returns_none_for_empty_pairs(self, db):
        """Empty pair list returns None."""
        strategy = _make_strategy(db)
        assert strategy._calculate_avg_score([], "levenshtein_score") is None

    @pytest.mark.unit
    def test_returns_none_when_field_missing(self, db):
        """If no pair contains the score field, returns None."""
        strategy = _make_strategy(db)
        pairs = [{"other_field": 1.0}]
        assert strategy._calculate_avg_score(pairs, "missing_field") is None


# ---------------------------------------------------------------------------
# generate_candidates
# ---------------------------------------------------------------------------

class TestHybridBlockingGenerateCandidates:
    """Tests for generate_candidates with mocked AQL."""

    @pytest.mark.unit
    def test_returns_empty_for_no_results(self, db):
        """No AQL results produces an empty list."""
        strategy = _make_strategy(db)
        assert strategy.generate_candidates() == []

    @pytest.mark.unit
    def test_normalises_and_returns_pairs(self, db):
        """Pairs from AQL are normalised (doc1_key < doc2_key)."""
        db.aql.execute.return_value = iter([
            {
                "doc1_key": "z",
                "doc2_key": "a",
                "levenshtein_score": 0.92,
                "bm25_score": 5.0,
                "combined_score": 4.5,
                "field_scores": {"name": 0.95},
                "search_fields": ["name"],
                "method": "hybrid_blocking",
            },
        ])
        strategy = _make_strategy(db)
        result = strategy.generate_candidates()

        assert len(result) == 1
        assert result[0]["doc1_key"] < result[0]["doc2_key"]

    @pytest.mark.unit
    def test_statistics_updated(self, db):
        """Statistics contain hybrid-specific keys after generation."""
        db.aql.execute.return_value = iter([
            {
                "doc1_key": "a",
                "doc2_key": "b",
                "levenshtein_score": 0.90,
                "bm25_score": 3.0,
                "combined_score": 2.8,
                "field_scores": {"name": 0.90},
                "search_fields": ["name"],
                "method": "hybrid_blocking",
            },
        ])
        strategy = _make_strategy(db)
        strategy.generate_candidates()
        stats = strategy.get_statistics()

        assert stats["total_pairs"] == 1
        assert stats["search_view"] == "companies_search"
        assert stats["levenshtein_threshold"] == 0.85


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------

class TestHybridBlockingRepr:
    """Tests for __repr__."""

    @pytest.mark.unit
    def test_repr_contains_key_info(self, db):
        """String representation includes collection, view, and thresholds."""
        strategy = _make_strategy(db)
        r = repr(strategy)
        assert "HybridBlockingStrategy" in r
        assert "companies" in r
        assert "companies_search" in r
        assert "0.85" in r
        assert "2.0" in r
