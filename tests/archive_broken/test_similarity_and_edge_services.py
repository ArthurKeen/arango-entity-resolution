"""
Unit tests for similarity and edge services.

Tests for:
- BatchSimilarityService
- SimilarityEdgeService
"""

import pytest
from entity_resolution.services.batch_similarity_service import BatchSimilarityService
from entity_resolution.services.similarity_edge_service import SimilarityEdgeService


class TestBatchSimilarityService:
    """Tests for BatchSimilarityService."""
    
    def test_initialization(self, db):
        """Test service initialization."""
        service = BatchSimilarityService(
            db=db,
            collection="test_collection",
            field_weights={"name": 0.6, "address": 0.4},
            similarity_algorithm="jaro_winkler"
        )
        
        assert service.collection == "test_collection"
        assert service.field_weights == {"name": 0.6, "address": 0.4}
        assert service.algorithm_name == "jaro_winkler"
    
    def test_weight_normalization(self, db):
        """Test that weights are normalized to sum to 1.0."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 2.0, "address": 3.0}  # Sum = 5.0
        )
        
        # Should be normalized
        assert service.field_weights["name"] == 0.4  # 2.0/5.0
        assert service.field_weights["address"] == 0.6  # 3.0/5.0
    
    def test_invalid_weights(self, db):
        """Test validation of field weights."""
        with pytest.raises(ValueError, match="Field weights cannot all be zero"):
            BatchSimilarityService(
                db=db,
                collection="test",
                field_weights={"name": 0.0, "address": 0.0}
            )
    
    def test_algorithm_setup_jaro_winkler(self, db):
        """Test Jaro-Winkler algorithm setup."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0},
            similarity_algorithm="jaro_winkler"
        )
        
        # Test the algorithm function
        score = service.similarity_algorithm("hello", "hallo")
        assert 0.0 <= score <= 1.0
        assert score > 0.8  # Should be high similarity
    
    def test_algorithm_setup_jaccard(self, db):
        """Test Jaccard algorithm setup."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0},
            similarity_algorithm="jaccard"
        )
        
        score = service.similarity_algorithm("hello world", "hello world")
        assert score == 1.0  # Exact match
    
    def test_algorithm_setup_custom(self, db):
        """Test custom algorithm setup."""
        def custom_algo(s1, s2):
            return 0.5 if s1 == s2 else 0.0
        
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0},
            similarity_algorithm=custom_algo
        )
        
        assert service.algorithm_name == "custom"
        assert service.similarity_algorithm("a", "a") == 0.5
        assert service.similarity_algorithm("a", "b") == 0.0
    
    def test_invalid_algorithm(self, db):
        """Test error handling for invalid algorithm."""
        with pytest.raises(ValueError, match="Unknown algorithm"):
            BatchSimilarityService(
                db=db,
                collection="test",
                field_weights={"name": 1.0},
                similarity_algorithm="invalid_algorithm"
            )
    
    def test_normalize_value(self, db):
        """Test value normalization."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0},
            normalization_config={
                "strip": True,
                "case": "upper",
                "remove_extra_whitespace": True
            }
        )
        
        normalized = service._normalize_value("  hello   world  ")
        assert normalized == "HELLO WORLD"
    
    def test_normalize_value_lowercase(self, db):
        """Test lowercase normalization."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0},
            normalization_config={"case": "lower"}
        )
        
        normalized = service._normalize_value("HELLO")
        assert normalized == "hello"
    
    def test_jaccard_similarity(self, db):
        """Test Jaccard similarity calculation."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0}
        )
        
        # Identical sets
        assert service._jaccard_similarity("a b c", "a b c") == 1.0
        
        # No overlap
        assert service._jaccard_similarity("a b", "c d") == 0.0
        
        # Partial overlap
        score = service._jaccard_similarity("a b c", "b c d")
        assert 0.4 < score < 0.7  # 2 common / 4 total
    
    def test_empty_candidate_pairs(self, db):
        """Test handling of empty candidate pairs."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0}
        )
        
        matches = service.compute_similarities([], threshold=0.75)
        assert matches == []
    
    def test_get_statistics(self, db):
        """Test statistics tracking."""
        service = BatchSimilarityService(
            db=db,
            collection="test",
            field_weights={"name": 1.0}
        )
        
        # Trigger statistics update
        service._update_statistics(100, 25, 50, 10.5)
        
        stats = service.get_statistics()
        assert stats['pairs_processed'] == 100
        assert stats['pairs_above_threshold'] == 25
        assert stats['documents_cached'] == 50
        assert stats['execution_time_seconds'] == 10.5
        assert 'pairs_per_second' in stats
        assert 'timestamp' in stats
    
    def test_repr(self, db):
        """Test string representation."""
        service = BatchSimilarityService(
            db=db,
            collection="test_collection",
            field_weights={"name": 0.6, "address": 0.4}
        )
        
        repr_str = repr(service)
        assert "BatchSimilarityService" in repr_str
        assert "test_collection" in repr_str
        assert "name, address" in repr_str


class TestSimilarityEdgeService:
    """Tests for SimilarityEdgeService."""
    
    def test_initialization(self, db):
        """Test service initialization."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection="similarTo",
            vertex_collection="companies",
            batch_size=500
        )
        
        assert service.edge_collection_name == "similarTo"
        assert service.vertex_collection == "companies"
        assert service.batch_size == 500
    
    def test_format_vertex_id(self, db):
        """Test vertex ID formatting."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection="similarTo",
            vertex_collection="companies"
        )
        
        # Simple key
        vertex_id = service._format_vertex_id("123")
        assert vertex_id == "companies/123"
        
        # Already formatted
        vertex_id = service._format_vertex_id("companies/123")
        assert vertex_id == "companies/123"
    
    def test_format_vertex_id_no_collection(self, db):
        """Test vertex ID formatting without collection."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection="similarTo",
            vertex_collection=None
        )
        
        vertex_id = service._format_vertex_id("123")
        assert vertex_id == "vertices/123"
    
    def test_empty_matches(self, db):
        """Test handling of empty matches."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection="similarTo"
        )
        
        edges_created = service.create_edges([])
        assert edges_created == 0
    
    def test_update_statistics(self, db):
        """Test statistics tracking."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection="similarTo"
        )
        
        service._update_statistics(1000, 10, 5.5)
        
        stats = service.get_statistics()
        assert stats['edges_created'] == 1000
        assert stats['batches_processed'] == 10
        assert stats['avg_batch_size'] == 100  # 1000/10
        assert stats['execution_time_seconds'] == 5.5
        assert 'edges_per_second' in stats
        assert 'timestamp' in stats
    
    def test_repr(self, db):
        """Test string representation."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection="similarTo",
            batch_size=500
        )
        
        repr_str = repr(service)
        assert "SimilarityEdgeService" in repr_str
        assert "similarTo" in repr_str
        assert "500" in repr_str


# Mock fixtures for testing
@pytest.fixture
def db():
    """Mock database fixture."""
    class MockDB:
        def __init__(self):
            self.collections = {}
        
        def has_collection(self, name):
            return name in self.collections
        
        def create_collection(self, name, edge=False):
            class MockCollection:
                def __init__(self, name):
                    self.name = name
                
                def insert_many(self, docs):
                    return len(docs)
            
            coll = MockCollection(name)
            self.collections[name] = coll
            return coll
        
        def collection(self, name):
            if name in self.collections:
                return self.collections[name]
            return self.create_collection(name)
    
    return MockDB()


# Integration tests would go in test_similarity_integration.py
# These would test with actual ArangoDB data and verify:
# - Actual document fetching
# - Real similarity computations
# - Edge creation in database
# - Performance characteristics

