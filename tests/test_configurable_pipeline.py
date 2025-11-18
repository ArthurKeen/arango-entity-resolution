"""
Unit Tests for ConfigurableERPipeline

Comprehensive tests for the configuration-driven ER pipeline.
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline
from entity_resolution.config.er_config import (
    ERPipelineConfig,
    BlockingConfig,
    SimilarityConfig,
    ClusteringConfig
)


class TestConfigurableERPipelineInitialization:
    """Test ConfigurableERPipeline initialization."""
    
    def test_init_with_config_object(self):
        """Test initialization with ERPipelineConfig object."""
        db_mock = Mock()
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        
        assert pipeline.db == db_mock
        assert pipeline.config == config
        assert pipeline.config.entity_type == "company"
        assert pipeline.config.collection_name == "companies"
    
    def test_init_with_config_path_yaml(self):
        """Test initialization with YAML config path."""
        db_mock = Mock()
        
        # Create temporary YAML file
        yaml_content = """
entity_type: company
collection_name: companies
edge_collection: similarTo
cluster_collection: clusters

blocking:
  strategy: exact
  max_block_size: 100
  min_block_size: 2
  fields: []

similarity:
  algorithm: jaro_winkler
  threshold: 0.75
  batch_size: 5000
  field_weights:
    name: 0.5
    address: 0.5

clustering:
  algorithm: wcc
  min_cluster_size: 2
  store_results: true
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            config_path = f.name
        
        try:
            pipeline = ConfigurableERPipeline(db=db_mock, config_path=config_path)
            
            assert pipeline.db == db_mock
            assert pipeline.config.entity_type == "company"
            assert pipeline.config.collection_name == "companies"
            assert pipeline.config.blocking.strategy == "exact"
            assert pipeline.config.similarity.threshold == 0.75
        finally:
            os.unlink(config_path)
    
    def test_init_with_config_path_json(self):
        """Test initialization with JSON config path."""
        db_mock = Mock()
        
        json_content = """{
  "entity_type": "company",
  "collection_name": "companies",
  "edge_collection": "similarTo",
  "cluster_collection": "clusters",
  "blocking": {
    "strategy": "exact",
    "max_block_size": 100,
    "min_block_size": 2,
    "fields": []
  },
  "similarity": {
    "algorithm": "jaro_winkler",
    "threshold": 0.75,
    "batch_size": 5000,
    "field_weights": {
      "name": 0.5,
      "address": 0.5
    }
  },
  "clustering": {
    "algorithm": "wcc",
    "min_cluster_size": 2,
    "store_results": true
  }
}"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json_content)
            config_path = f.name
        
        try:
            pipeline = ConfigurableERPipeline(db=db_mock, config_path=config_path)
            
            assert pipeline.db == db_mock
            assert pipeline.config.entity_type == "company"
        finally:
            os.unlink(config_path)
    
    def test_init_without_config_or_path(self):
        """Test that initialization fails without config or path."""
        db_mock = Mock()
        
        with pytest.raises(ValueError, match="Either config or config_path must be provided"):
            ConfigurableERPipeline(db=db_mock)
    
    def test_init_with_invalid_config_path(self):
        """Test that initialization fails with non-existent config path."""
        db_mock = Mock()
        
        with pytest.raises(FileNotFoundError):
            ConfigurableERPipeline(db=db_mock, config_path="/nonexistent/path.yaml")
    
    def test_init_validates_config(self):
        """Test that initialization validates configuration."""
        db_mock = Mock()
        
        # Create invalid config (missing required fields)
        config = ERPipelineConfig(
            entity_type="",  # Invalid: empty
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            ConfigurableERPipeline(db=db_mock, config=config)
    
    def test_repr(self):
        """Test string representation."""
        db_mock = Mock()
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        
        repr_str = repr(pipeline)
        assert "ConfigurableERPipeline" in repr_str
        assert "company" in repr_str
        assert "companies" in repr_str


class TestConfigurableERPipelineBlocking:
    """Test blocking phase of ConfigurableERPipeline."""
    
    @patch('entity_resolution.core.configurable_pipeline.CollectBlockingStrategy')
    def test_run_blocking_exact_strategy(self, mock_strategy_class):
        """Test blocking with exact strategy."""
        db_mock = Mock()
        mock_strategy = Mock()
        mock_strategy.generate_candidates.return_value = [
            {'doc1_key': 'a', 'doc2_key': 'b'},
            {'doc1_key': 'c', 'doc2_key': 'd'}
        ]
        mock_strategy_class.return_value = mock_strategy
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(strategy="exact"),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        pairs = pipeline._run_blocking()
        
        assert len(pairs) == 2
        assert mock_strategy_class.called
        assert mock_strategy.generate_candidates.called
    
    @patch('entity_resolution.core.configurable_pipeline.BM25BlockingStrategy')
    def test_run_blocking_bm25_strategy(self, mock_strategy_class):
        """Test blocking with BM25 strategy."""
        db_mock = Mock()
        mock_strategy = Mock()
        mock_strategy.generate_candidates.return_value = [
            {'doc1_key': 'x', 'doc2_key': 'y'}
        ]
        mock_strategy_class.return_value = mock_strategy
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(strategy="bm25"),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        pairs = pipeline._run_blocking()
        
        assert len(pairs) == 1
        assert mock_strategy_class.called
    
    def test_run_blocking_unknown_strategy(self):
        """Test blocking with unknown strategy."""
        db_mock = Mock()
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(strategy="unknown"),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        pairs = pipeline._run_blocking()
        
        assert pairs == []


class TestConfigurableERPipelineSimilarity:
    """Test similarity phase of ConfigurableERPipeline."""
    
    @patch('entity_resolution.core.configurable_pipeline.BatchSimilarityService')
    def test_run_similarity(self, mock_service_class):
        """Test similarity computation."""
        db_mock = Mock()
        mock_service = Mock()
        mock_service.compute_similarities.return_value = [
            ('a', 'b', 0.85),
            ('c', 'd', 0.92)
        ]
        mock_service_class.return_value = mock_service
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(
                algorithm="jaro_winkler",
                threshold=0.75,
                field_weights={"name": 0.5, "address": 0.5}
            ),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        matches = pipeline._run_similarity([('a', 'b'), ('c', 'd')])
        
        assert len(matches) == 2
        assert mock_service_class.called
        assert mock_service.compute_similarities.called
    
    def test_run_similarity_empty_pairs(self):
        """Test similarity with empty candidate pairs."""
        db_mock = Mock()
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        matches = pipeline._run_similarity([])
        
        assert matches == []


class TestConfigurableERPipelineEdgeCreation:
    """Test edge creation phase of ConfigurableERPipeline."""
    
    @patch('entity_resolution.core.configurable_pipeline.SimilarityEdgeService')
    @patch('entity_resolution.core.configurable_pipeline.time')
    def test_run_edge_creation(self, mock_time, mock_service_class):
        """Test edge creation."""
        db_mock = Mock()
        mock_time.strftime.return_value = "2025-11-17T12:00:00"
        
        mock_service = Mock()
        mock_service.create_edges.return_value = 5
        mock_service_class.return_value = mock_service
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            edge_collection="similarTo",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        edges_created = pipeline._run_edge_creation([
            ('a', 'b', 0.85),
            ('c', 'd', 0.92)
        ])
        
        assert edges_created == 5
        assert mock_service_class.called
        assert mock_service.create_edges.called
        
        # Check metadata
        call_args = mock_service.create_edges.call_args
        assert 'metadata' in call_args[1]
        assert call_args[1]['metadata']['method'] == 'configurable_pipeline'
    
    def test_run_edge_creation_empty_matches(self):
        """Test edge creation with empty matches."""
        db_mock = Mock()
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        edges_created = pipeline._run_edge_creation([])
        
        assert edges_created == 0


class TestConfigurableERPipelineClustering:
    """Test clustering phase of ConfigurableERPipeline."""
    
    @patch('entity_resolution.core.configurable_pipeline.WCCClusteringService')
    def test_run_clustering(self, mock_service_class):
        """Test clustering."""
        db_mock = Mock()
        mock_service = Mock()
        mock_service.cluster.return_value = [
            ['a', 'b'],
            ['c', 'd', 'e']
        ]
        mock_service_class.return_value = mock_service
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            edge_collection="similarTo",
            cluster_collection="clusters",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig(
                min_cluster_size=2,
                store_results=True
            )
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        clusters = pipeline._run_clustering()
        
        assert len(clusters) == 2
        assert mock_service_class.called
        assert mock_service.cluster.called


class TestConfigurableERPipelineAddressER:
    """Test address ER pipeline."""
    
    @patch('entity_resolution.core.configurable_pipeline.AddressERService')
    def test_run_address_er(self, mock_service_class):
        """Test address ER pipeline execution."""
        db_mock = Mock()
        mock_service = Mock()
        mock_service.run.return_value = {
            'blocks_found': 5,
            'addresses_matched': 10,
            'edges_created': 8,
            'clusters_found': 3,
            'runtime_seconds': 2.5
        }
        mock_service_class.return_value = mock_service
        
        config = ERPipelineConfig(
            entity_type="address",
            collection_name="addresses",
            edge_collection="address_sameAs",
            blocking=BlockingConfig(max_block_size=100),
            similarity=SimilarityConfig(batch_size=5000),
            clustering=ClusteringConfig(min_cluster_size=2, store_results=True)
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        results = pipeline._run_address_er({}, 0.0)
        
        assert mock_service_class.called
        assert mock_service.setup_infrastructure.called
        assert mock_service.run.called
        
        assert results['blocking']['blocks_found'] == 5
        assert results['edges']['edges_created'] == 8
        assert results['clustering']['clusters_found'] == 3


class TestConfigurableERPipelineRun:
    """Test complete pipeline execution."""
    
    @patch('entity_resolution.core.configurable_pipeline.CollectBlockingStrategy')
    @patch('entity_resolution.core.configurable_pipeline.BatchSimilarityService')
    @patch('entity_resolution.core.configurable_pipeline.SimilarityEdgeService')
    @patch('entity_resolution.core.configurable_pipeline.WCCClusteringService')
    @patch('entity_resolution.core.configurable_pipeline.time')
    def test_run_complete_pipeline(
        self,
        mock_time,
        mock_wcc_class,
        mock_edge_class,
        mock_sim_class,
        mock_block_class
    ):
        """Test complete pipeline execution."""
        db_mock = Mock()
        mock_time.time.side_effect = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        mock_time.strftime.return_value = "2025-11-17T12:00:00"
        
        # Mock blocking
        mock_block_strategy = Mock()
        mock_block_strategy.generate_candidates.return_value = [
            {'doc1_key': 'a', 'doc2_key': 'b'}
        ]
        mock_block_class.return_value = mock_block_strategy
        
        # Mock similarity
        mock_sim_service = Mock()
        mock_sim_service.compute_similarities.return_value = [('a', 'b', 0.85)]
        mock_sim_class.return_value = mock_sim_service
        
        # Mock edge creation
        mock_edge_service = Mock()
        mock_edge_service.create_edges.return_value = 1
        mock_edge_class.return_value = mock_edge_service
        
        # Mock clustering
        mock_wcc_service = Mock()
        mock_wcc_service.cluster.return_value = [['a', 'b']]
        mock_wcc_class.return_value = mock_wcc_service
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            edge_collection="similarTo",
            cluster_collection="clusters",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig(store_results=True)
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        results = pipeline.run()
        
        # Verify results structure
        assert 'blocking' in results
        assert 'similarity' in results
        assert 'edges' in results
        assert 'clustering' in results
        assert 'total_runtime_seconds' in results
        
        # Verify values
        assert results['blocking']['candidate_pairs'] == 1
        assert results['similarity']['matches_found'] == 1
        assert results['edges']['edges_created'] == 1
        assert results['clustering']['clusters_found'] == 1
    
    @patch('entity_resolution.core.configurable_pipeline.CollectBlockingStrategy')
    def test_run_pipeline_no_similarity_config(self, mock_block_class):
        """Test pipeline with no similarity config."""
        db_mock = Mock()
        mock_block_strategy = Mock()
        mock_block_strategy.generate_candidates.return_value = []
        mock_block_class.return_value = mock_block_strategy
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=None,  # No similarity config
            clustering=ClusteringConfig()
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        results = pipeline.run()
        
        assert results['similarity']['matches_found'] == 0
        assert results['edges']['edges_created'] == 0
    
    @patch('entity_resolution.core.configurable_pipeline.CollectBlockingStrategy')
    def test_run_pipeline_no_clustering(self, mock_block_class):
        """Test pipeline with clustering disabled."""
        db_mock = Mock()
        mock_block_strategy = Mock()
        mock_block_strategy.generate_candidates.return_value = []
        mock_block_class.return_value = mock_block_strategy
        
        config = ERPipelineConfig(
            entity_type="company",
            collection_name="companies",
            blocking=BlockingConfig(),
            similarity=SimilarityConfig(),
            clustering=ClusteringConfig(store_results=False)
        )
        
        pipeline = ConfigurableERPipeline(db=db_mock, config=config)
        results = pipeline.run()
        
        assert results['clustering']['clusters_found'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

