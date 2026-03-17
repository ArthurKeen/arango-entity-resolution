"""
Unit tests for blocking strategies.

Tests for:
- BlockingStrategy (base class)
- CollectBlockingStrategy
- BM25BlockingStrategy
"""

import pytest
from entity_resolution.strategies import (
    BlockingStrategy,
    CollectBlockingStrategy,
    BM25BlockingStrategy
)


class MockBlockingStrategy(BlockingStrategy):
    """Mock implementation for testing base class."""
    
    def generate_candidates(self):
        return [
            {'doc1_key': 'a', 'doc2_key': 'b'},
            {'doc1_key': 'c', 'doc2_key': 'd'}
        ]


class TestBlockingStrategy:
    """Tests for base BlockingStrategy class."""
    
    def test_initialization(self, db):
        """Test base strategy initialization."""
        strategy = MockBlockingStrategy(
            db=db,
            collection="test_collection",
            filters={"field1": {"not_null": True}}
        )
        
        assert strategy.db == db
        assert strategy.collection == "test_collection"
        assert strategy.filters == {"field1": {"not_null": True}}
        assert strategy._stats['strategy_name'] == 'MockBlockingStrategy'
    
    def test_build_filter_conditions(self, db):
        """Test filter condition building."""
        strategy = MockBlockingStrategy(db=db, collection="test")
        
        filters = {
            "field1": {"not_null": True},
            "field2": {"min_length": 5},
            "field3": {"not_equal": ["val1", "val2"]},
            "field4": {"equals": "exact_value"}
        }
        
        conditions, bind_vars = strategy._build_filter_conditions(filters)

        assert "d.field1 != null" in conditions
        assert "LENGTH(d.field2) >= 5" in conditions
        assert any("d.field3 != @" in c for c in conditions)
        assert any("d.field4 == @" in c for c in conditions)
        # String values must be in bind_vars, not interpolated into query strings
        assert any(v == "val1" for v in bind_vars.values())
        assert any(v == "val2" for v in bind_vars.values())
        assert any(v == "exact_value" for v in bind_vars.values())
    
    def test_normalize_pairs(self, db):
        """Test pair normalization."""
        strategy = MockBlockingStrategy(db=db, collection="test")
        
        pairs = [
            {'doc1_key': 'b', 'doc2_key': 'a'},  # Should be swapped
            {'doc1_key': 'a', 'doc2_key': 'b'},  # Duplicate (after swap)
            {'doc1_key': 'c', 'doc2_key': 'd'}
        ]
        
        normalized = strategy._normalize_pairs(pairs)
        
        assert len(normalized) == 2  # One duplicate removed
        
        # Check all pairs are normalized (doc1_key < doc2_key)
        for pair in normalized:
            assert pair['doc1_key'] < pair['doc2_key']
    
    def test_get_statistics(self, db):
        """Test statistics retrieval."""
        strategy = MockBlockingStrategy(db=db, collection="test")
        pairs = strategy.generate_candidates()
        strategy._update_statistics(pairs, 1.5)
        
        stats = strategy.get_statistics()
        
        assert stats['total_pairs'] == 2
        assert stats['execution_time_seconds'] == 1.5
        assert stats['strategy_name'] == 'MockBlockingStrategy'
        assert 'timestamp' in stats


class TestCollectBlockingStrategy:
    """Tests for CollectBlockingStrategy."""
    
    def test_initialization(self, db):
        """Test initialization with valid parameters."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["field1", "field2"],
            filters={"field1": {"not_null": True}},
            max_block_size=50,
            min_block_size=2
        )
        
        assert strategy.blocking_fields == ["field1", "field2"]
        assert strategy.max_block_size == 50
        assert strategy.min_block_size == 2
    
    def test_initialization_validation(self, db):
        """Test parameter validation."""
        # Empty blocking fields
        with pytest.raises(ValueError, match="blocking_fields cannot be empty"):
            CollectBlockingStrategy(
                db=db,
                collection="test",
                blocking_fields=[]
            )
        
        # Invalid min_block_size
        with pytest.raises(ValueError, match="min_block_size must be at least 2"):
            CollectBlockingStrategy(
                db=db,
                collection="test",
                blocking_fields=["field1"],
                min_block_size=1
            )
        
        # max_block_size < min_block_size
        with pytest.raises(ValueError, match="max_block_size must be >= min_block_size"):
            CollectBlockingStrategy(
                db=db,
                collection="test",
                blocking_fields=["field1"],
                min_block_size=10,
                max_block_size=5
            )
    
    def test_build_collect_query(self, db):
        """Test AQL query generation."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["phone", "state"],
            filters={
                "phone": {"not_null": True, "min_length": 10},
                "state": {"not_null": True}
            },
            max_block_size=100,
            min_block_size=2
        )
        
        query, bind_vars = strategy._build_collect_query()
        
        # Check query contains expected components
        assert "FOR d IN test_collection" in query
        assert "COLLECT phone = d.phone, state = d.state" in query
        assert "INTO group" in query
        assert "KEEP d" in query
        assert "LET doc_keys = group[*].d._key" in query
        assert "FILTER LENGTH(doc_keys) >= 2" in query
        assert "FILTER LENGTH(doc_keys) <= 100" in query
        assert "d.phone != null" in query
        assert "LENGTH(d.phone) >= 10" in query
        assert "d.state != null" in query
    
    def test_build_collect_query_with_computed_fields(self, db):
        """Test query generation with computed fields."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["zip5", "state"],
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
        )
        
        query, bind_vars = strategy._build_collect_query()
        
        assert "LET _computed_zip5 = LEFT(d.postal_code, 5)" in query
        assert "COLLECT zip5 = _computed_zip5, state = d.state" in query
    
    def test_exclude_values_in_query(self, db):
        """Test that exclude_values generates NOT IN filter in AQL."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["address", "state"],
            exclude_values={
                "address": {"401 E 8TH STREET", "300 N DAKOTA AVE"}
            }
        )
        
        query, bind_vars = strategy._build_collect_query()
        
        assert "FILTER d.address NOT IN @_excl_address" in query
        assert "_excl_address" in bind_vars
        assert sorted(bind_vars["_excl_address"]) == ["300 N DAKOTA AVE", "401 E 8TH STREET"]
    
    def test_exclude_values_with_computed_field(self, db):
        """Test exclusion on a computed field references the temp variable."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["zip5", "state"],
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"},
            exclude_values={"zip5": {"00000"}}
        )
        
        query, bind_vars = strategy._build_collect_query()
        
        assert "FILTER _computed_zip5 NOT IN @_excl_zip5" in query
        assert bind_vars["_excl_zip5"] == ["00000"]
    
    def test_exclude_values_empty_set_skipped(self, db):
        """Test that an empty exclusion set produces no filter."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["address"],
            exclude_values={"address": set()}
        )
        
        query, bind_vars = strategy._build_collect_query()
        
        assert "NOT IN" not in query
        assert "_excl_address" not in bind_vars
    
    def test_exclude_values_default_none(self, db):
        """Test that exclude_values defaults to empty dict."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["field1"]
        )
        
        assert strategy.exclude_values == {}
    
    def test_exclude_values_in_statistics(self, db):
        """Test that exclusion counts appear in statistics."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["address"],
            exclude_values={"address": {"ADDR1", "ADDR2", "ADDR3"}}
        )
        
        pairs = strategy.generate_candidates()
        stats = strategy.get_statistics()
        
        assert stats["excluded_value_counts"] == {"address": 3}
    
    def test_exclude_values_multiple_fields(self, db):
        """Test exclusion across multiple fields."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["address", "state"],
            exclude_values={
                "address": {"401 E 8TH STREET"},
                "state": {"XX"}
            }
        )
        
        query, bind_vars = strategy._build_collect_query()
        
        assert "FILTER d.address NOT IN @_excl_address" in query
        assert "FILTER d.state NOT IN @_excl_state" in query
        assert bind_vars["_excl_address"] == ["401 E 8TH STREET"]
        assert bind_vars["_excl_state"] == ["XX"]
    
    def test_repr(self, db):
        """Test string representation."""
        strategy = CollectBlockingStrategy(
            db=db,
            collection="test_collection",
            blocking_fields=["field1", "field2"]
        )
        
        repr_str = repr(strategy)
        assert "CollectBlockingStrategy" in repr_str
        assert "test_collection" in repr_str
        assert "field1, field2" in repr_str


class TestBM25BlockingStrategy:
    """Tests for BM25BlockingStrategy."""
    
    def test_initialization(self, db):
        """Test initialization with valid parameters."""
        strategy = BM25BlockingStrategy(
            db=db,
            collection="test_collection",
            search_view="test_view",
            search_field="name",
            bm25_threshold=2.0,
            limit_per_entity=20,
            blocking_field="state",
            analyzer="text_en"
        )
        
        assert strategy.collection == "test_collection"
        assert strategy.search_view == "test_view"
        assert strategy.search_field == "name"
        assert strategy.bm25_threshold == 2.0
        assert strategy.limit_per_entity == 20
        assert strategy.blocking_field == "state"
        assert strategy.analyzer == "text_en"
    
    def test_initialization_validation(self, db):
        """Test parameter validation."""
        # Empty search_view
        with pytest.raises(ValueError, match="search_view cannot be empty"):
            BM25BlockingStrategy(
                db=db,
                collection="test",
                search_view="",
                search_field="name"
            )
        
        # Empty search_field
        with pytest.raises(ValueError, match="search_field cannot be empty"):
            BM25BlockingStrategy(
                db=db,
                collection="test",
                search_view="view",
                search_field=""
            )
        
        # Invalid bm25_threshold
        with pytest.raises(ValueError, match="bm25_threshold must be positive"):
            BM25BlockingStrategy(
                db=db,
                collection="test",
                search_view="view",
                search_field="name",
                bm25_threshold=-1.0
            )
        
        # Invalid limit_per_entity
        with pytest.raises(ValueError, match="limit_per_entity must be positive"):
            BM25BlockingStrategy(
                db=db,
                collection="test",
                search_view="view",
                search_field="name",
                limit_per_entity=0
            )
    
    def test_build_bm25_query(self, db):
        """Test AQL query generation."""
        strategy = BM25BlockingStrategy(
            db=db,
            collection="test_collection",
            search_view="test_view",
            search_field="name",
            bm25_threshold=2.0,
            limit_per_entity=20,
            blocking_field="state",
            filters={
                "name": {"not_null": True, "min_length": 3},
                "state": {"not_null": True}
            }
        )
        
        query = strategy._build_bm25_query()
        
        # Check query contains expected components
        assert "FOR d1 IN test_collection" in query
        assert "FOR d2 IN test_view" in query
        assert "SEARCH ANALYZER(" in query
        assert "PHRASE(d2.name, d1.name" in query
        assert "LET bm25_score = BM25(d2)" in query
        assert "FILTER bm25_score > @bm25_threshold" in query
        assert "FILTER d2.state == d1.state" in query
        assert "FILTER d1._key < d2._key" in query
        assert "LIMIT @limit_per_entity" in query
        assert "d1.name != null" in query
        assert "LENGTH(d1.name) > 3" in query
    
    def test_calculate_avg_bm25_score(self, db):
        """Test BM25 score statistics calculation."""
        strategy = BM25BlockingStrategy(
            db=db,
            collection="test",
            search_view="view",
            search_field="name"
        )
        
        pairs = [
            {'bm25_score': 3.0},
            {'bm25_score': 5.0},
            {'bm25_score': 4.0}
        ]
        
        avg_score = strategy._calculate_avg_bm25_score(pairs)
        assert avg_score == 4.0
        
        # Empty pairs
        assert strategy._calculate_avg_bm25_score([]) is None
    
    def test_calculate_max_bm25_score(self, db):
        """Test max BM25 score calculation."""
        strategy = BM25BlockingStrategy(
            db=db,
            collection="test",
            search_view="view",
            search_field="name"
        )
        
        pairs = [
            {'bm25_score': 3.0},
            {'bm25_score': 5.0},
            {'bm25_score': 4.0}
        ]
        
        max_score = strategy._calculate_max_bm25_score(pairs)
        assert max_score == 5.0
        
        # Empty pairs
        assert strategy._calculate_max_bm25_score([]) is None
    
    def test_repr(self, db):
        """Test string representation."""
        strategy = BM25BlockingStrategy(
            db=db,
            collection="test_collection",
            search_view="test_view",
            search_field="name",
            bm25_threshold=2.5
        )
        
        repr_str = repr(strategy)
        assert "BM25BlockingStrategy" in repr_str
        assert "test_collection" in repr_str
        assert "test_view" in repr_str
        assert "name" in repr_str
        assert "2.5" in repr_str


# Mock fixtures for testing
@pytest.fixture
def db():
    """Mock database fixture."""
    class MockCollection:
        def __init__(self, name):
            self.name = name
        
        def all(self):
            return []
    
    class MockAQL:
        def execute(self, query, bind_vars=None):
            return []
    
    class MockDB:
        def __init__(self):
            self.collections = {}
            self.aql = MockAQL()
        
        def has_collection(self, name):
            return name in self.collections
        
        def create_collection(self, name, edge=False):
            coll = MockCollection(name)
            self.collections[name] = coll
            return coll
        
        def collection(self, name):
            if name in self.collections:
                return self.collections[name]
            return MockCollection(name)
    
    return MockDB()


# Integration tests would go in a separate file (test_blocking_integration.py)
# These would test with actual ArangoDB data

