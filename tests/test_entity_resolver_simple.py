"""
Simplified Entity Resolution Pipeline Tests

Tests the actual EntityResolutionPipeline API methods.
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
        assert pipeline.data_manager is not None
        assert pipeline.blocking_service is not None
        assert pipeline.similarity_service is not None
        assert pipeline.clustering_service is not None
    
    def test_initialization_custom_config(self):
        """Test pipeline initializes with custom config"""
        config = Config()
        pipeline = EntityResolutionPipeline(config)
        
        assert pipeline.config == config
    
    def test_initial_state(self):
        """Test pipeline initial state"""
        pipeline = EntityResolutionPipeline()
        
        assert pipeline.connected == False
        assert isinstance(pipeline.pipeline_stats, dict)


class TestEntityResolutionPipelineConnection:
    """Test database connection"""
    
    def test_connect_without_database(self):
        """Test connect method exists and handles no database gracefully"""
        pipeline = EntityResolutionPipeline()
        
        # Just test that connect method exists and returns a boolean
        result = pipeline.connect()
        
        # Should return False if database not available
        assert isinstance(result, bool)
    
    @patch('entity_resolution.data.data_manager.DataManager')
    def test_connect_failure(self, mock_data_manager):
        """Test connection failure"""
        # Setup mock - data manager fails to connect
        mock_dm = Mock()
        mock_dm.connect.return_value = False
        mock_data_manager.return_value = mock_dm
        
        pipeline = EntityResolutionPipeline()
        result = pipeline.connect()
        
        assert result is False


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


class TestEntityResolutionPipelinePerformance:
    """Test performance characteristics"""
    
    def test_pipeline_initialization_fast(self):
        """Test that pipeline initialization is fast"""
        import time
        
        start = time.time()
        pipeline = EntityResolutionPipeline()
        init_time = time.time() - start
        
        # Should initialize in < 0.1 seconds
        assert init_time < 0.1


class TestEntityResolutionPipelineComponents:
    """Test pipeline components"""
    
    def test_has_all_components(self):
        """Test pipeline has all required components"""
        pipeline = EntityResolutionPipeline()
        
        # Verify all services are initialized
        assert pipeline.data_manager is not None
        assert pipeline.blocking_service is not None
        assert pipeline.similarity_service is not None
        assert pipeline.clustering_service is not None
    
    def test_services_are_correct_type(self):
        """Test services are correct types"""
        from entity_resolution.data.data_manager import DataManager
        from entity_resolution.services.blocking_service import BlockingService
        from entity_resolution.services.similarity_service import SimilarityService
        from entity_resolution.services.clustering_service import ClusteringService
        
        pipeline = EntityResolutionPipeline()
        
        assert isinstance(pipeline.data_manager, DataManager)
        assert isinstance(pipeline.blocking_service, BlockingService)
        assert isinstance(pipeline.similarity_service, SimilarityService)
        assert isinstance(pipeline.clustering_service, ClusteringService)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

