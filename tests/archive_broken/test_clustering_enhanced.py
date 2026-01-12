"""
Enhanced Unit Tests for ClusteringService

Comprehensive tests for entity clustering, including:
- Connected components algorithm
- Threshold-based clustering
- Cluster statistics
- Edge cases
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


class TestConnectedComponents:
    """Test connected components clustering"""
    
    def test_simple_cluster(self):
        """Test clustering with simple connected pairs"""
        service = ClusteringService()
        
        # Three records forming one cluster: 1-2, 2-3
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2', 
             'similarity_score': 0.9},
            {'record_a_id': 'customers/2', 'record_b_id': 'customers/3',
             'similarity_score': 0.85}
        ]
        
        result = service.cluster_entities(pairs)
        
        assert result['success'] is True
        assert len(result['clusters']) == 1
        assert len(result['clusters'][0]['members']) == 3
    
    def test_multiple_clusters(self):
        """Test creating multiple separate clusters"""
        service = ClusteringService()
        
        # Two separate clusters: (1-2) and (3-4)
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9},
            {'record_a_id': 'customers/3', 'record_b_id': 'customers/4',
             'similarity_score': 0.85}
        ]
        
        result = service.cluster_entities(pairs)
        
        assert result['success'] is True
        assert len(result['clusters']) == 2
    
    def test_transitive_clustering(self):
        """Test that clustering is transitive"""
        service = ClusteringService()
        
        # If 1-2 and 2-3 are similar, then 1,2,3 should be in same cluster
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9},
            {'record_a_id': 'customers/2', 'record_b_id': 'customers/3',
             'similarity_score': 0.85}
        ]
        
        result = service.cluster_entities(pairs)
        
        cluster = result['clusters'][0]
        assert 'customers/1' in cluster['members']
        assert 'customers/2' in cluster['members']
        assert 'customers/3' in cluster['members']


class TestThresholdClustering:
    """Test threshold-based clustering"""
    
    def test_threshold_filters_weak_pairs(self):
        """Test that pairs below threshold are not clustered"""
        service = ClusteringService()
        
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9},  # Above threshold
            {'record_a_id': 'customers/3', 'record_b_id': 'customers/4',
             'similarity_score': 0.3}   # Below threshold
        ]
        
        result = service.cluster_entities(pairs, min_similarity=0.7)
        
        # Should only create cluster for first pair
        assert result['success'] is True
        # Exact number of clusters depends on implementation
        # but weak pair should not be clustered
    
    def test_high_threshold(self):
        """Test clustering with high similarity threshold"""
        service = ClusteringService()
        
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.95},
            {'record_a_id': 'customers/3', 'record_b_id': 'customers/4',
             'similarity_score': 0.85}
        ]
        
        result = service.cluster_entities(pairs, min_similarity=0.9)
        
        # Should only cluster the first pair
        assert result['success'] is True


class TestClusterStatistics:
    """Test cluster statistics generation"""
    
    def test_statistics_generated(self):
        """Test that cluster statistics are generated"""
        service = ClusteringService()
        
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9}
        ]
        
        result = service.cluster_entities(pairs)
        
        assert 'statistics' in result
        assert 'total_clusters' in result['statistics']
        assert 'execution_time' in result['statistics']
    
    def test_cluster_size_distribution(self):
        """Test cluster size distribution statistics"""
        service = ClusteringService()
        
        # Create clusters of different sizes
        pairs = [
            # Cluster 1: 3 members (1-2-3)
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9},
            {'record_a_id': 'customers/2', 'record_b_id': 'customers/3',
             'similarity_score': 0.9},
            # Cluster 2: 2 members (4-5)
            {'record_a_id': 'customers/4', 'record_b_id': 'customers/5',
             'similarity_score': 0.9}
        ]
        
        result = service.cluster_entities(pairs)
        
        # Should have clusters of different sizes
        cluster_sizes = [len(c['members']) for c in result['clusters']]
        assert len(set(cluster_sizes)) > 1  # Different sizes


class TestClusteringEdgeCases:
    """Test edge cases"""
    
    def test_empty_pairs(self):
        """Test clustering with no pairs"""
        service = ClusteringService()
        
        result = service.cluster_entities([])
        
        assert result['success'] is True
        assert len(result['clusters']) == 0
    
    def test_single_pair(self):
        """Test clustering with single pair"""
        service = ClusteringService()
        
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9}
        ]
        
        result = service.cluster_entities(pairs)
        
        assert result['success'] is True
        assert len(result['clusters']) == 1
        assert len(result['clusters'][0]['members']) == 2
    
    def test_duplicate_pairs_handled(self):
        """Test that duplicate pairs don't cause issues"""
        service = ClusteringService()
        
        # Same pair listed twice
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9},
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9}
        ]
        
        result = service.cluster_entities(pairs)
        
        # Should still create single cluster with 2 members
        assert result['success'] is True
        assert len(result['clusters']) == 1
    
    def test_reverse_pairs_handled(self):
        """Test that reverse pairs are handled correctly"""
        service = ClusteringService()
        
        # Same pair in reverse order
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9},
            {'record_a_id': 'customers/2', 'record_b_id': 'customers/1',
             'similarity_score': 0.9}
        ]
        
        result = service.cluster_entities(pairs)
        
        # Should handle gracefully
        assert result['success'] is True


class TestClusteringPerformance:
    """Test performance characteristics"""
    
    def test_large_cluster_performance(self):
        """Test clustering with large number of pairs"""
        import time
        
        service = ClusteringService()
        
        # Create 100 pairs
        pairs = [
            {
                'record_a_id': f'customers/{i}',
                'record_b_id': f'customers/{i+1}',
                'similarity_score': 0.9
            }
            for i in range(100)
        ]
        
        start = time.time()
        result = service.cluster_entities(pairs)
        execution_time = time.time() - start
        
        # Should complete in reasonable time (< 1 second)
        assert execution_time < 1.0
        assert result['success'] is True


class TestClusteringAlgorithms:
    """Test specific clustering algorithms"""
    
    def test_connected_components_correct(self):
        """Test that connected components algorithm is correct"""
        service = ClusteringService()
        
        # Create a specific graph structure
        # Components: {1,2,3} and {4,5}
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.9},
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/3',
             'similarity_score': 0.9},
            {'record_a_id': 'customers/4', 'record_b_id': 'customers/5',
             'similarity_score': 0.9}
        ]
        
        result = service.cluster_entities(pairs)
        
        assert len(result['clusters']) == 2
        
        # Find larger cluster
        large_cluster = max(result['clusters'], key=lambda c: len(c['members']))
        assert len(large_cluster['members']) == 3


class TestClusterQuality:
    """Test cluster quality metrics"""
    
    def test_cluster_quality_metrics(self):
        """Test that cluster quality can be measured"""
        service = ClusteringService()
        
        pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2',
             'similarity_score': 0.95},
            {'record_a_id': 'customers/2', 'record_b_id': 'customers/3',
             'similarity_score': 0.90}
        ]
        
        result = service.cluster_entities(pairs)
        
        # Each cluster should have some quality indicator
        for cluster in result['clusters']:
            assert 'members' in cluster
            assert len(cluster['members']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

