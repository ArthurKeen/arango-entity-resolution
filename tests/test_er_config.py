"""
Unit Tests for ER Configuration System

Comprehensive tests for ERPipelineConfig and related configuration classes.
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.config.er_config import (
    ERPipelineConfig,
    BlockingConfig,
    SimilarityConfig,
    ClusteringConfig
)


class TestBlockingConfig:
    """Test cases for BlockingConfig."""
    
    def test_initialization_defaults(self):
        """Test initialization with defaults."""
        config = BlockingConfig()
        
        assert config.strategy == 'exact'
        assert config.max_block_size == 100
        assert config.min_block_size == 2
        assert config.fields == []
    
    def test_initialization_custom(self):
        """Test initialization with custom values."""
        config = BlockingConfig(
            strategy='bm25',
            max_block_size=50,
            min_block_size=3,
            fields=[{'name': 'field1'}]
        )
        
        assert config.strategy == 'bm25'
        assert config.max_block_size == 50
        assert config.min_block_size == 3
        assert len(config.fields) == 1
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        config_dict = {
            'strategy': 'arangosearch',
            'max_block_size': 200,
            'min_block_size': 2,
            'fields': []
        }
        
        config = BlockingConfig.from_dict(config_dict)
        
        assert config.strategy == 'arangosearch'
        assert config.max_block_size == 200
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = BlockingConfig(
            strategy='exact',
            max_block_size=100
        )
        
        config_dict = config.to_dict()
        
        assert config_dict['strategy'] == 'exact'
        assert config_dict['max_block_size'] == 100


class TestSimilarityConfig:
    """Test cases for SimilarityConfig."""
    
    def test_initialization_defaults(self):
        """Test initialization with defaults."""
        config = SimilarityConfig()
        
        assert config.algorithm == 'jaro_winkler'
        assert config.threshold == 0.75
        assert config.batch_size == 5000
        assert config.field_weights == {}
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        config_dict = {
            'algorithm': 'levenshtein',
            'threshold': 0.8,
            'batch_size': 1000,
            'field_weights': {'name': 0.5, 'address': 0.5}
        }
        
        config = SimilarityConfig.from_dict(config_dict)
        
        assert config.algorithm == 'levenshtein'
        assert config.threshold == 0.8
        assert config.field_weights['name'] == 0.5


class TestClusteringConfig:
    """Test cases for ClusteringConfig."""
    
    def test_initialization_defaults(self):
        """Test initialization with defaults."""
        config = ClusteringConfig()
        
        assert config.algorithm == 'wcc'
        assert config.min_cluster_size == 2
        assert config.store_results is True
        assert config.wcc_algorithm == 'python_dfs'
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        config_dict = {
            'algorithm': 'wcc',
            'min_cluster_size': 3,
            'store_results': False,
            'wcc_algorithm': 'aql_graph'
        }
        
        config = ClusteringConfig.from_dict(config_dict)
        
        assert config.min_cluster_size == 3
        assert config.store_results is False
        assert config.wcc_algorithm == 'aql_graph'


class TestERPipelineConfig:
    """Test cases for ERPipelineConfig."""
    
    def test_initialization(self):
        """Test basic initialization."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses'
        )
        
        assert config.entity_type == 'address'
        assert config.collection_name == 'addresses'
        assert config.edge_collection == 'similarTo'
        assert isinstance(config.blocking, BlockingConfig)
        assert isinstance(config.similarity, SimilarityConfig)
        assert isinstance(config.clustering, ClusteringConfig)
    
    def test_from_dict_simple(self):
        """Test creation from simple dictionary."""
        config_dict = {
            'entity_type': 'person',
            'collection_name': 'people',
            'edge_collection': 'person_sameAs'
        }
        
        config = ERPipelineConfig.from_dict(config_dict)
        
        assert config.entity_type == 'person'
        assert config.collection_name == 'people'
        assert config.edge_collection == 'person_sameAs'
    
    def test_from_dict_nested(self):
        """Test creation from nested dictionary (with 'entity_resolution' key)."""
        config_dict = {
            'entity_resolution': {
                'entity_type': 'company',
                'collection_name': 'companies',
                'blocking': {
                    'strategy': 'exact',
                    'max_block_size': 100
                },
                'similarity': {
                    'algorithm': 'jaro_winkler',
                    'threshold': 0.75
                }
            }
        }
        
        config = ERPipelineConfig.from_dict(config_dict)
        
        assert config.entity_type == 'company'
        assert config.blocking.strategy == 'exact'
        assert config.similarity.algorithm == 'jaro_winkler'
    
    def test_from_yaml(self):
        """Test loading from YAML file."""
        yaml_content = """
entity_resolution:
  entity_type: "address"
  collection_name: "addresses"
  edge_collection: "address_sameAs"
  blocking:
    strategy: "arangosearch"
    max_block_size: 100
  similarity:
    algorithm: "jaro_winkler"
    threshold: 0.75
    field_weights:
      street: 0.5
      city: 0.3
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ERPipelineConfig.from_yaml(temp_path)
            
            assert config.entity_type == 'address'
            assert config.collection_name == 'addresses'
            assert config.blocking.strategy == 'arangosearch'
            assert config.similarity.field_weights['street'] == 0.5
        finally:
            os.unlink(temp_path)
    
    def test_from_yaml_file_not_found(self):
        """Test error when YAML file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            ERPipelineConfig.from_yaml('/nonexistent/path/config.yaml')
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses',
            blocking=BlockingConfig(max_block_size=100, min_block_size=2),
            similarity=SimilarityConfig(threshold=0.75),
            clustering=ClusteringConfig(min_cluster_size=2)
        )
        
        errors = config.validate()
        assert len(errors) == 0
    
    def test_validate_invalid_blocking(self):
        """Test validation catches invalid blocking config."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses',
            blocking=BlockingConfig(max_block_size=10, min_block_size=20)  # Invalid
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any('max_block_size' in e for e in errors)
    
    def test_validate_invalid_threshold(self):
        """Test validation catches invalid similarity threshold."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses',
            similarity=SimilarityConfig(threshold=1.5)  # Invalid (> 1.0)
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any('threshold' in e for e in errors)
    
    def test_validate_invalid_algorithm(self):
        """Test validation catches invalid algorithm."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses',
            similarity=SimilarityConfig(algorithm='invalid_algorithm')
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any('algorithm' in e for e in errors)
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses'
        )
        
        config_dict = config.to_dict()
        
        assert 'entity_resolution' in config_dict
        assert config_dict['entity_resolution']['entity_type'] == 'address'
        assert config_dict['entity_resolution']['collection_name'] == 'addresses'
    
    def test_to_yaml(self):
        """Test conversion to YAML."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses'
        )
        
        yaml_str = config.to_yaml()
        
        assert 'entity_resolution' in yaml_str
        assert 'address' in yaml_str
        assert 'addresses' in yaml_str
    
    def test_to_yaml_file_output(self):
        """Test writing YAML to file."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses'
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            yaml_str = config.to_yaml(output_path=temp_path)
            
            assert Path(temp_path).exists()
            assert 'entity_resolution' in yaml_str
            
            # Verify we can read it back
            loaded_config = ERPipelineConfig.from_yaml(temp_path)
            assert loaded_config.entity_type == 'address'
        finally:
            if Path(temp_path).exists():
                os.unlink(temp_path)
    
    def test_repr(self):
        """Test string representation."""
        config = ERPipelineConfig(
            entity_type='address',
            collection_name='addresses'
        )
        
        repr_str = repr(config)
        assert 'ERPipelineConfig' in repr_str
        assert 'address' in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

