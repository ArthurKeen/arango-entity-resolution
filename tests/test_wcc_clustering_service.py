"""
Unit tests for WCC clustering service.

Tests for:
- WCCClusteringService
"""

import pytest
from entity_resolution.services.wcc_clustering_service import WCCClusteringService


class TestWCCClusteringService:
    """Tests for WCCClusteringService."""
    
    def test_initialization(self, db):
        """Test service initialization."""
        service = WCCClusteringService(
            db=db,
            edge_collection="similarTo",
            cluster_collection="entity_clusters",
            vertex_collection="companies",
            min_cluster_size=2
        )
        
        assert service.edge_collection_name == "similarTo"
        assert service.cluster_collection_name == "entity_clusters"
        assert service.vertex_collection == "companies"
        assert service.min_cluster_size == 2
    
    def test_format_vertex_id(self, db):
        """Test vertex ID formatting."""
        service = WCCClusteringService(
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
    
    def test_extract_key_from_vertex_id(self, db):
        """Test key extraction from vertex ID."""
        service = WCCClusteringService(
            db=db,
            edge_collection="similarTo"
        )
        
        # Full vertex ID
        key = service._extract_key_from_vertex_id("companies/123")
        assert key == "123"
        
        # Already a key
        key = service._extract_key_from_vertex_id("123")
        assert key == "123"
    
    def test_update_statistics_empty(self, db):
        """Test statistics with empty clusters."""
        service = WCCClusteringService(
            db=db,
            edge_collection="similarTo"
        )
        
        service._update_statistics([], 1.5)
        
        stats = service.get_statistics()
        assert stats['total_clusters'] == 0
        assert stats['total_entities_clustered'] == 0
        assert stats['execution_time_seconds'] == 1.5
    
    def test_update_statistics_with_clusters(self, db):
        """Test statistics with actual clusters."""
        service = WCCClusteringService(
            db=db,
            edge_collection="similarTo"
        )
        
        clusters = [
            ["a", "b"],           # Size 2
            ["c", "d", "e"],      # Size 3
            ["f", "g", "h", "i"], # Size 4
            ["j", "k"]            # Size 2
        ]
        
        service._update_statistics(clusters, 3.5)
        
        stats = service.get_statistics()
        assert stats['total_clusters'] == 4
        assert stats['total_entities_clustered'] == 11  # 2+3+4+2
        assert stats['avg_cluster_size'] == 2.75  # 11/4
        assert stats['max_cluster_size'] == 4
        assert stats['min_cluster_size'] == 2
        assert stats['execution_time_seconds'] == 3.5
        
        # Check size distribution
        dist = stats['cluster_size_distribution']
        assert dist['2'] == 2  # Two clusters of size 2
        assert dist['3'] == 1  # One cluster of size 3
        assert dist['4-10'] == 1  # One cluster of size 4
    
    def test_repr(self, db):
        """Test string representation."""
        service = WCCClusteringService(
            db=db,
            edge_collection="similarTo",
            min_cluster_size=3
        )
        
        repr_str = repr(service)
        assert "WCCClusteringService" in repr_str
        assert "similarTo" in repr_str
        assert "3" in repr_str


# Mock fixtures for testing
@pytest.fixture
def db():
    """Mock database fixture."""
    class MockCollection:
        def __init__(self, name):
            self.name = name
            self.docs = []
        
        def truncate(self):
            self.docs = []
        
        def insert_many(self, docs):
            self.docs.extend(docs)
            return len(docs)
        
        def all(self, limit=None):
            return self.docs[:limit] if limit else self.docs
        
        def __iter__(self):
            return iter(self.docs)
    
    class MockAQL:
        def execute(self, query, bind_vars=None):
            # Return empty results for test
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
            if name not in self.collections:
                self.collections[name] = MockCollection(name)
            return self.collections[name]
    
    return MockDB()


# Integration tests would test:
# - Actual graph traversal with real edges
# - Cluster storage in database
# - Validation against real data
# - Performance with various graph sizes

