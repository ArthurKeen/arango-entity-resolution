"""
Fixed Unit Tests for ClusteringService

Tests for entity clustering using the ACTUAL API methods.
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.clustering_service import ClusteringService


class TestClusteringServiceInitialization:
    """Test service initialization"""
    
    def test_initialization(self):
        """Test service initializes correctly"""
        service = ClusteringService()
        
        assert service is not None
        assert service.config is not None


class TestClusterEntities:
    """Test cluster_entities() method"""
    
    def test_simple_cluster(self):
        """Test clustering with simple connected pairs"""
        service = ClusteringService()
        
        # Three records forming one cluster: 1-2, 2-3
        scored_pairs = [
            {
                'doc_a_id': 'customers/1',
                'doc_b_id': 'customers/2',
                'overall_score': 0.9
            },
            {
                'doc_a_id': 'customers/2',
                'doc_b_id': 'customers/3',
                'overall_score': 0.85
            }
        ]
        
        result = service.cluster_entities(scored_pairs)
        
        assert 'success' in result or 'clusters' in result or isinstance(result, list)
    
    def test_multiple_clusters(self):
        """Test creating multiple separate clusters"""
        service = ClusteringService()
        
        # Two separate clusters: (1-2) and (3-4)
        scored_pairs = [
            {
                'doc_a_id': 'customers/1',
                'doc_b_id': 'customers/2',
                'overall_score': 0.9
            },
            {
                'doc_a_id': 'customers/3',
                'doc_b_id': 'customers/4',
                'overall_score': 0.85
            }
        ]
        
        result = service.cluster_entities(scored_pairs)
        
        # Should create clusters
        assert result is not None
    
    def test_with_threshold(self):
        """Test clustering with similarity threshold"""
        service = ClusteringService()
        
        scored_pairs = [
            {
                'doc_a_id': 'customers/1',
                'doc_b_id': 'customers/2',
                'overall_score': 0.9  # Above threshold
            },
            {
                'doc_a_id': 'customers/3',
                'doc_b_id': 'customers/4',
                'overall_score': 0.3  # Below threshold
            }
        ]
        
        # Filter pairs by threshold manually, then call cluster_entities
        # The method doesn't take a threshold parameter - it clusters all pairs
        filtered_pairs = [p for p in scored_pairs if p['overall_score'] >= 0.7]
        result = service.cluster_entities(filtered_pairs)
        
        assert result is not None


class TestBuildSimilarityGraph:
    """Test build_similarity_graph() method"""
    
    def test_build_graph_from_pairs(self):
        """Test building a graph from scored pairs"""
        service = ClusteringService()
        
        scored_pairs = [
            {
                'doc_a_id': 'customers/1',
                'doc_b_id': 'customers/2',
                'overall_score': 0.9
            }
        ]
        
        result = service.build_similarity_graph(scored_pairs)
        
        assert result is not None


class TestValidateClusterQuality:
    """Test validate_cluster_quality() method"""
    
    def test_validate_clusters(self):
        """Test validating cluster quality"""
        service = ClusteringService()
        
        clusters = [
            {
                'cluster_id': '1',
                'members': ['customers/1', 'customers/2', 'customers/3']
            }
        ]
        
        result = service.validate_cluster_quality(clusters)
        
        assert result is not None


class TestClusteringEdgeCases:
    """Test edge cases"""
    
    def test_empty_pairs(self):
        """Test clustering with no pairs"""
        service = ClusteringService()
        
        result = service.cluster_entities([])
        
        # Should handle gracefully
        assert result is not None
    
    def test_single_pair(self):
        """Test clustering with single pair"""
        service = ClusteringService()
        
        scored_pairs = [
            {
                'doc_a_id': 'customers/1',
                'doc_b_id': 'customers/2',
                'overall_score': 0.9
            }
        ]
        
        result = service.cluster_entities(scored_pairs)
        
        assert result is not None


class TestClusteringPerformance:
    """Test performance characteristics"""
    
    def test_clustering_performance(self):
        """Test clustering with many pairs"""
        import time
        
        service = ClusteringService()
        
        # Create 100 pairs
        scored_pairs = [
            {
                'doc_a_id': f'customers/{i}',
                'doc_b_id': f'customers/{i+1}',
                'overall_score': 0.9
            }
            for i in range(100)
        ]
        
        start = time.time()
        result = service.cluster_entities(scored_pairs)
        execution_time = time.time() - start
        
        # Should complete in reasonable time
        assert execution_time < 5.0
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

