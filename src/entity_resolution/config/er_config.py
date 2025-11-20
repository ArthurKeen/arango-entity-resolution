"""
Entity Resolution Pipeline Configuration

Provides configuration classes for defining ER pipelines via YAML/JSON.
Supports validation, defaults, and environment variable overrides.
"""

from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import yaml
import json
import logging

from ..utils.constants import DEFAULT_SIMILARITY_THRESHOLD, DEFAULT_BATCH_SIZE


class BlockingConfig:
    """Blocking configuration."""
    
    def __init__(
        self,
        strategy: str = "exact",
        max_block_size: int = 100,
        min_block_size: int = 2,
        fields: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Initialize blocking configuration.
        
        Args:
            strategy: Blocking strategy ("exact", "arangosearch", "bm25")
            max_block_size: Maximum addresses per block
            min_block_size: Minimum addresses per block
            fields: List of field configurations for blocking
        """
        self.strategy = strategy
        self.max_block_size = max_block_size
        self.min_block_size = min_block_size
        self.fields = fields or []
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'BlockingConfig':
        """Create from dictionary."""
        return cls(
            strategy=config_dict.get('strategy', 'exact'),
            max_block_size=config_dict.get('max_block_size', 100),
            min_block_size=config_dict.get('min_block_size', 2),
            fields=config_dict.get('fields', [])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy': self.strategy,
            'max_block_size': self.max_block_size,
            'min_block_size': self.min_block_size,
            'fields': self.fields
        }


class SimilarityConfig:
    """Similarity configuration."""
    
    def __init__(
        self,
        algorithm: str = "jaro_winkler",
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        batch_size: int = DEFAULT_BATCH_SIZE,
        field_weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize similarity configuration.
        
        Args:
            algorithm: Similarity algorithm ("jaro_winkler", "levenshtein", "jaccard")
            threshold: Minimum similarity threshold (0.0-1.0). Default DEFAULT_SIMILARITY_THRESHOLD (0.75).
            batch_size: Batch size for similarity computation. Default DEFAULT_BATCH_SIZE (5000).
            field_weights: Dictionary of field names to weights
        """
        self.algorithm = algorithm
        self.threshold = threshold
        self.batch_size = batch_size
        self.field_weights = field_weights or {}
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'SimilarityConfig':
        """Create from dictionary."""
        return cls(
            algorithm=config_dict.get('algorithm', 'jaro_winkler'),
            threshold=config_dict.get('threshold', DEFAULT_SIMILARITY_THRESHOLD),
            batch_size=config_dict.get('batch_size', DEFAULT_BATCH_SIZE),
            field_weights=config_dict.get('field_weights', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'algorithm': self.algorithm,
            'threshold': self.threshold,
            'batch_size': self.batch_size,
            'field_weights': self.field_weights
        }


class ClusteringConfig:
    """Clustering configuration."""
    
    def __init__(
        self,
        algorithm: str = "wcc",
        min_cluster_size: int = 2,
        store_results: bool = True,
        wcc_algorithm: str = "python_dfs"
    ):
        """
        Initialize clustering configuration.
        
        Args:
            algorithm: Clustering algorithm ("wcc")
            min_cluster_size: Minimum entities per cluster
            store_results: Whether to store cluster results
            wcc_algorithm: WCC algorithm ("python_dfs" or "aql_graph")
        """
        self.algorithm = algorithm
        self.min_cluster_size = min_cluster_size
        self.store_results = store_results
        self.wcc_algorithm = wcc_algorithm
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ClusteringConfig':
        """Create from dictionary."""
        return cls(
            algorithm=config_dict.get('algorithm', 'wcc'),
            min_cluster_size=config_dict.get('min_cluster_size', 2),
            store_results=config_dict.get('store_results', True),
            wcc_algorithm=config_dict.get('wcc_algorithm', 'python_dfs')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'algorithm': self.algorithm,
            'min_cluster_size': self.min_cluster_size,
            'store_results': self.store_results,
            'wcc_algorithm': self.wcc_algorithm
        }


class ERPipelineConfig:
    """
    Complete ER pipeline configuration.
    
    Supports loading from YAML/JSON files and provides validation.
    
    Example YAML:
        ```yaml
        entity_resolution:
          entity_type: "address"
          collection_name: "addresses"
          edge_collection: "address_sameAs"
          cluster_collection: "address_clusters"
          
          blocking:
            strategy: "arangosearch"
            max_block_size: 100
            min_block_size: 2
          
          similarity:
            algorithm: "jaro_winkler"
            threshold: 0.75  # Use DEFAULT_SIMILARITY_THRESHOLD in code
            field_weights:
              street: 0.5
              city: 0.3
              state: 0.1
              postal_code: 0.1
          
          clustering:
            algorithm: "wcc"
            min_cluster_size: 2
            wcc_algorithm: "python_dfs"
        ```
    """
    
    def __init__(
        self,
        entity_type: str,
        collection_name: str,
        edge_collection: str = "similarTo",
        cluster_collection: str = "entity_clusters",
        blocking: Optional[BlockingConfig] = None,
        similarity: Optional[SimilarityConfig] = None,
        clustering: Optional[ClusteringConfig] = None
    ):
        """
        Initialize ER pipeline configuration.
        
        Args:
            entity_type: Type of entity ("address", "person", "company", etc.)
            collection_name: Source collection name
            edge_collection: Edge collection name
            cluster_collection: Cluster collection name
            blocking: Blocking configuration
            similarity: Similarity configuration
            clustering: Clustering configuration
        """
        self.entity_type = entity_type
        self.collection_name = collection_name
        self.edge_collection = edge_collection
        self.cluster_collection = cluster_collection
        
        self.blocking = blocking or BlockingConfig()
        self.similarity = similarity or SimilarityConfig()
        self.clustering = clustering or ClusteringConfig()
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> 'ERPipelineConfig':
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML configuration file
        
        Returns:
            ERPipelineConfig instance
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        
        return cls.from_dict(config_dict)
    
    @classmethod
    def from_json(cls, config_path: Union[str, Path]) -> 'ERPipelineConfig':
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to JSON configuration file
        
        Returns:
            ERPipelineConfig instance
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config_dict = json.load(f)
        
        return cls.from_dict(config_dict)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ERPipelineConfig':
        """
        Load configuration from dictionary.
        
        Args:
            config_dict: Configuration dictionary (may have 'entity_resolution' key)
        
        Returns:
            ERPipelineConfig instance
        """
        # Handle nested 'entity_resolution' key
        if 'entity_resolution' in config_dict:
            config_dict = config_dict['entity_resolution']
        
        # Extract sub-configurations
        blocking_config = BlockingConfig.from_dict(
            config_dict.get('blocking', {})
        )
        similarity_config = SimilarityConfig.from_dict(
            config_dict.get('similarity', {})
        )
        clustering_config = ClusteringConfig.from_dict(
            config_dict.get('clustering', {})
        )
        
        return cls(
            entity_type=config_dict.get('entity_type', 'entity'),
            collection_name=config_dict.get('collection_name', 'entities'),
            edge_collection=config_dict.get('edge_collection', 'similarTo'),
            cluster_collection=config_dict.get('cluster_collection', 'entity_clusters'),
            blocking=blocking_config,
            similarity=similarity_config,
            clustering=clustering_config
        )
    
    def validate(self) -> List[str]:
        """
        Validate configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate blocking
        if self.blocking.max_block_size < self.blocking.min_block_size:
            errors.append(
                f"blocking.max_block_size ({self.blocking.max_block_size}) must be >= "
                f"blocking.min_block_size ({self.blocking.min_block_size})"
            )
        
        if self.blocking.strategy not in ('exact', 'arangosearch', 'bm25'):
            errors.append(
                f"blocking.strategy must be 'exact', 'arangosearch', or 'bm25', "
                f"got: {self.blocking.strategy}"
            )
        
        # Validate similarity
        if not 0.0 <= self.similarity.threshold <= 1.0:
            errors.append(
                f"similarity.threshold must be between 0.0 and 1.0, "
                f"got: {self.similarity.threshold}"
            )
        
        if self.similarity.algorithm not in ('jaro_winkler', 'levenshtein', 'jaccard'):
            errors.append(
                f"similarity.algorithm must be 'jaro_winkler', 'levenshtein', or 'jaccard', "
                f"got: {self.similarity.algorithm}"
            )
        
        if self.similarity.field_weights:
            if not all(w >= 0 for w in self.similarity.field_weights.values()):
                errors.append("similarity.field_weights must be non-negative")
        
        # Validate clustering
        if self.clustering.algorithm not in ('wcc',):
            errors.append(
                f"clustering.algorithm must be 'wcc', got: {self.clustering.algorithm}"
            )
        
        if self.clustering.wcc_algorithm not in ('python_dfs', 'aql_graph'):
            errors.append(
                f"clustering.wcc_algorithm must be 'python_dfs' or 'aql_graph', "
                f"got: {self.clustering.wcc_algorithm}"
            )
        
        if self.clustering.min_cluster_size < 1:
            errors.append(
                f"clustering.min_cluster_size must be >= 1, "
                f"got: {self.clustering.min_cluster_size}"
            )
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entity_resolution': {
                'entity_type': self.entity_type,
                'collection_name': self.collection_name,
                'edge_collection': self.edge_collection,
                'cluster_collection': self.cluster_collection,
                'blocking': self.blocking.to_dict(),
                'similarity': self.similarity.to_dict(),
                'clustering': self.clustering.to_dict()
            }
        }
    
    def to_yaml(self, output_path: Optional[Union[str, Path]] = None) -> str:
        """
        Convert to YAML string or write to file.
        
        Args:
            output_path: Optional path to write YAML file
        
        Returns:
            YAML string
        """
        yaml_str = yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)
        
        if output_path:
            output_path = Path(output_path)
            with open(output_path, 'w') as f:
                f.write(yaml_str)
        
        return yaml_str
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"ERPipelineConfig("
                f"entity_type='{self.entity_type}', "
                f"collection='{self.collection_name}')")

