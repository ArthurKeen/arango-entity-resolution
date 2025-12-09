"""
Entity Resolution System for ArangoDB

A complete entity resolution system that combines:
- Python orchestration and data processing
- ArangoDB native storage and querying
- Graph-based clustering algorithms
- Unified demo and presentation capabilities

Main components:
- EntityResolver: Main orchestration class
- BlockingService: Record blocking and candidate generation
- SimilarityService: Fellegi-Sunter similarity computation
- ClusteringService: Graph-based entity clustering
- DataManager: Data ingestion and management
- DatabaseManager: Centralized database connection management
"""

# Import version from constants
from .utils.constants import get_version_string
__version__ = get_version_string()
__author__ = "Entity Resolution Team"

# Core components
from .core.entity_resolver import EntityResolver
from .core.configurable_pipeline import ConfigurableERPipeline
from .services.blocking_service import BlockingService
from .services.similarity_service import SimilarityService
from .services.clustering_service import ClusteringService
from .services.golden_record_service import GoldenRecordService
from .services.base_service import BaseEntityResolutionService
from .data.data_manager import DataManager

# New enhanced services (v2.0)
from .strategies import (
    BlockingStrategy,
    CollectBlockingStrategy,
    BM25BlockingStrategy,
    HybridBlockingStrategy,
    GeographicBlockingStrategy,
    GraphTraversalBlockingStrategy,
    VectorBlockingStrategy
)
from .services.batch_similarity_service import BatchSimilarityService
from .services.similarity_edge_service import SimilarityEdgeService
from .services.wcc_clustering_service import WCCClusteringService
from .services.address_er_service import AddressERService
from .services.cross_collection_matching_service import CrossCollectionMatchingService
from .services.embedding_service import EmbeddingService

# Similarity components (v3.0)
from .similarity.weighted_field_similarity import WeightedFieldSimilarity

# Pipeline utilities
from .utils.pipeline_utils import (
    clean_er_results,
    count_inferred_edges,
    validate_edge_quality,
    get_pipeline_statistics
)

# Configuration and utilities
from .utils.config import Config
from .config import (
    ERPipelineConfig,
    BlockingConfig,
    SimilarityConfig,
    ClusteringConfig
)
from .utils.database import DatabaseManager, get_database_manager, get_database
from .utils.constants import (
    DEFAULT_DATABASE_CONFIG,
    SIMILARITY_THRESHOLDS,
    ALGORITHM_WEIGHTS
)

# Demo capabilities
from .demo import (
    get_demo_manager,
    run_presentation_demo,
    run_automated_demo
)

__all__ = [
    # Core services
    'EntityResolver',
    'ConfigurableERPipeline',
    'BlockingService', 
    'SimilarityService',
    'ClusteringService',
    'GoldenRecordService',
    'BaseEntityResolutionService',
    'DataManager',
    
    # Enhanced services (v2.0)
    'BlockingStrategy',
    'CollectBlockingStrategy',
    'BM25BlockingStrategy',
    'HybridBlockingStrategy',
    'GeographicBlockingStrategy',
    'GraphTraversalBlockingStrategy',
    'VectorBlockingStrategy',
    'BatchSimilarityService',
    'SimilarityEdgeService',
    'WCCClusteringService',
    'AddressERService',
    'CrossCollectionMatchingService',
    'EmbeddingService',
    
    # Similarity components (v3.0)
    'WeightedFieldSimilarity',
    
    # Pipeline utilities
    'clean_er_results',
    'count_inferred_edges',
    'validate_edge_quality',
    'get_pipeline_statistics',
    
    # Configuration
    'Config',
    'ERPipelineConfig',
    'BlockingConfig',
    'SimilarityConfig',
    'ClusteringConfig',
    
    # Database utilities
    'DatabaseManager',
    'get_database_manager',
    'get_database',
    
    # Constants
    'DEFAULT_DATABASE_CONFIG',
    'SIMILARITY_THRESHOLDS',
    'ALGORITHM_WEIGHTS',
    
    # Demo capabilities
    'get_demo_manager',
    'run_presentation_demo',
    'run_automated_demo'
]
