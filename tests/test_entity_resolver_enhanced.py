"""
Enhanced Unit Tests for EntityResolutionPipeline

Comprehensive tests covering the complete entity resolution pipeline,
including blocking, similarity, and clustering stages.
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.core.entity_resolver import EntityResolutionPipeline
from entity_resolution.utils.config import Config


class TestEntityResolutionPipelineInitialization:
    """Test pipeline initialization"""
    
    def test_initialization_default_config(self):
        """Test pipeline initializes with default config"""
        pipeline = EntityResolutionPipeline()
        
        assert pipeline is not None
        assert pipeline.config is not None
        assert pipeline.logger is not None
    
    def test_initialization_custom_config(self):
        """Test pipeline initializes with custom config"""
        config = Config()
        pipeline = EntityResolutionPipeline(config)
        
        assert pipeline.config == config


class TestEntityResolutionPipelineConnection:
    """Test database connection"""
    
    @patch('entity_resolution.core.entity_resolver.ArangoClient')
    def test_connect_success(self, mock_client_class):
        """Test successful database connection"""
        mock_client = Mock()
        mock_db = Mock()
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        pipeline = EntityResolutionPipeline()
        result = pipeline.connect()
        
        assert result is True
    
    @patch('entity_resolution.core.entity_resolver.ArangoClient')
    def test_connect_failure(self, mock_client_class):
        """Test connection failure handling"""
        mock_client = Mock()
        mock_client.db.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client
        
        pipeline = EntityResolutionPipeline()
        result = pipeline.connect()
        
        assert result is False


class TestEntityResolutionPipelineBlocking:
    """Test blocking stage"""
    
    @patch('entity_resolution.services.bulk_blocking_service.BulkBlockingService')
    def test_blocking_stage_execution(self, mock_blocking_service):
        """Test blocking stage executes correctly"""
        # Setup mock
        mock_service = Mock()
        mock_service.generate_all_pairs.return_value = {
            'success': True,
            'candidate_pairs': [
                {'record_a_id': 'customers/1', 'record_b_id': 'customers/2'}
            ]
        }
        mock_blocking_service.return_value = mock_service
        
        pipeline = EntityResolutionPipeline()
        result = pipeline._run_blocking_stage(
            records=[{'_id': 'customers/1'}, {'_id': 'customers/2'}],
            collection_name="customers"
        )
        
        assert result['success'] is True
        assert 'candidate_pairs' in result
    
    def test_blocking_strategies_configurable(self):
        """Test that blocking strategies are configurable"""
        pipeline = EntityResolutionPipeline()
        
        # Should have default strategies
        assert pipeline.config.er.blocking_strategies is not None


class TestEntityResolutionPipelineSimilarity:
    """Test similarity scoring stage"""
    
    @patch('entity_resolution.services.similarity_service.SimilarityService')
    def test_similarity_stage_execution(self, mock_similarity_service):
        """Test similarity stage executes correctly"""
        # Setup mock
        mock_service = Mock()
        mock_service.compute_similarities.return_value = {
            'success': True,
            'scored_pairs': [
                {
                    'record_a_id': 'customers/1',
                    'record_b_id': 'customers/2',
                    'similarity_score': 0.85
                }
            ]
        }
        mock_similarity_service.return_value = mock_service
        
        pipeline = EntityResolutionPipeline()
        
        candidate_pairs = [
            {'record_a_id': 'customers/1', 'record_b_id': 'customers/2'}
        ]
        
        result = pipeline._run_similarity_stage(candidate_pairs)
        
        assert result['success'] is True
        assert 'scored_pairs' in result


class TestEntityResolutionPipelineClustering:
    """Test clustering stage"""
    
    @patch('entity_resolution.services.clustering_service.ClusteringService')
    def test_clustering_stage_execution(self, mock_clustering_service):
        """Test clustering stage executes correctly"""
        # Setup mock
        mock_service = Mock()
        mock_service.cluster_entities.return_value = {
            'success': True,
            'clusters': [
                {'cluster_id': '1', 'members': ['customers/1', 'customers/2']}
            ]
        }
        mock_clustering_service.return_value = mock_service
        
        pipeline = EntityResolutionPipeline()
        
        scored_pairs = [
            {
                'record_a_id': 'customers/1',
                'record_b_id': 'customers/2',
                'similarity_score': 0.85
            }
        ]
        
        result = pipeline._run_clustering_stage(scored_pairs)
        
        assert result['success'] is True
        assert 'clusters' in result


class TestEntityResolutionPipelineEndToEnd:
    """Test complete pipeline execution"""
    
    @patch('entity_resolution.services.clustering_service.ClusteringService')
    @patch('entity_resolution.services.similarity_service.SimilarityService')
    @patch('entity_resolution.services.bulk_blocking_service.BulkBlockingService')
    @patch('entity_resolution.core.entity_resolver.ArangoClient')
    def test_complete_pipeline_execution(
        self,
        mock_client_class,
        mock_blocking_service,
        mock_similarity_service,
        mock_clustering_service
    ):
        """Test complete pipeline from start to finish"""
        # Setup mocks
        # Database
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.all.return_value = [
            {'_id': 'customers/1', 'name': 'John Smith'},
            {'_id': 'customers/2', 'name': 'J. Smith'}
        ]
        mock_db.collection.return_value = mock_collection
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        # Blocking
        mock_blocking = Mock()
        mock_blocking.generate_all_pairs.return_value = {
            'success': True,
            'candidate_pairs': [
                {'record_a_id': 'customers/1', 'record_b_id': 'customers/2'}
            ]
        }
        mock_blocking_service.return_value = mock_blocking
        
        # Similarity
        mock_similarity = Mock()
        mock_similarity.compute_similarities.return_value = {
            'success': True,
            'scored_pairs': [
                {
                    'record_a_id': 'customers/1',
                    'record_b_id': 'customers/2',
                    'similarity_score': 0.85
                }
            ]
        }
        mock_similarity_service.return_value = mock_similarity
        
        # Clustering
        mock_clustering = Mock()
        mock_clustering.cluster_entities.return_value = {
            'success': True,
            'clusters': [
                {'cluster_id': '1', 'members': ['customers/1', 'customers/2']}
            ]
        }
        mock_clustering_service.return_value = mock_clustering
        
        # Execute pipeline
        pipeline = EntityResolutionPipeline()
        pipeline.connect()
        
        result = pipeline.resolve(collection_name="customers")
        
        assert result['success'] is True
        assert 'clusters' in result
        assert len(result['clusters']) == 1


class TestEntityResolutionPipelineErrorHandling:
    """Test error handling"""
    
    @patch('entity_resolution.services.bulk_blocking_service.BulkBlockingService')
    def test_blocking_failure_handled(self, mock_blocking_service):
        """Test pipeline handles blocking failures"""
        mock_service = Mock()
        mock_service.generate_all_pairs.return_value = {
            'success': False,
            'error': 'Blocking failed'
        }
        mock_blocking_service.return_value = mock_service
        
        pipeline = EntityResolutionPipeline()
        
        result = pipeline._run_blocking_stage([], "customers")
        
        assert result['success'] is False
    
    @patch('entity_resolution.services.similarity_service.SimilarityService')
    def test_similarity_failure_handled(self, mock_similarity_service):
        """Test pipeline handles similarity failures"""
        mock_service = Mock()
        mock_service.compute_similarities.return_value = {
            'success': False,
            'error': 'Similarity computation failed'
        }
        mock_similarity_service.return_value = mock_service
        
        pipeline = EntityResolutionPipeline()
        
        result = pipeline._run_similarity_stage([])
        
        assert result['success'] is False
    
    def test_empty_collection_handled(self):
        """Test pipeline handles empty collections"""
        pipeline = EntityResolutionPipeline()
        
        result = pipeline._run_blocking_stage([], "customers")
        
        # Should handle gracefully, not crash
        assert 'success' in result


class TestEntityResolutionPipelineConfiguration:
    """Test configuration management"""
    
    def test_default_configuration(self):
        """Test default configuration is loaded"""
        pipeline = EntityResolutionPipeline()
        
        assert pipeline.config is not None
        assert hasattr(pipeline.config, 'er')
        assert hasattr(pipeline.config, 'db')
    
    def test_custom_configuration(self):
        """Test custom configuration is used"""
        config = Config()
        config.er.similarity_threshold = 0.9
        
        pipeline = EntityResolutionPipeline(config)
        
        assert pipeline.config.er.similarity_threshold == 0.9
    
    def test_configuration_validation(self):
        """Test configuration is validated"""
        pipeline = EntityResolutionPipeline()
        
        # Should have valid configuration
        assert pipeline.config.er.similarity_threshold > 0.0
        assert pipeline.config.er.similarity_threshold <= 1.0


class TestEntityResolutionPipelineStatistics:
    """Test statistics generation"""
    
    @patch('entity_resolution.services.bulk_blocking_service.BulkBlockingService')
    def test_statistics_generation(self, mock_blocking_service):
        """Test that pipeline generates statistics"""
        mock_service = Mock()
        mock_service.generate_all_pairs.return_value = {
            'success': True,
            'candidate_pairs': [],
            'statistics': {
                'total_pairs': 0,
                'execution_time': 1.5,
                'pairs_per_second': 0
            }
        }
        mock_blocking_service.return_value = mock_service
        
        pipeline = EntityResolutionPipeline()
        result = pipeline._run_blocking_stage([], "customers")
        
        assert 'statistics' in result


class TestEntityResolutionPipelinePerformance:
    """Test performance characteristics"""
    
    def test_pipeline_not_slow(self):
        """Test that pipeline initialization is fast"""
        import time
        
        start = time.time()
        pipeline = EntityResolutionPipeline()
        init_time = time.time() - start
        
        # Should initialize in < 0.1 seconds
        assert init_time < 0.1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

