"""
Entity Resolution System for ArangoDB

A complete entity resolution system that combines:
- Python orchestration and data processing
- ArangoDB native storage and querying
- Graph-based clustering algorithms
- Unified demo and presentation capabilities

Main components are lazily imported to improve startup time and avoid
unnecessary dependency loading.
"""

def __getattr__(name):
    if name == "__version__":
        from .utils.constants import get_version_string
        return get_version_string()
    
    if name == "__author__":
        return "Entity Resolution Team"

    # Core components
    if name == "EntityResolver":
        from .core.entity_resolver import EntityResolver
        return EntityResolver
    if name == "ConfigurableERPipeline":
        from .core.configurable_pipeline import ConfigurableERPipeline
        return ConfigurableERPipeline
    if name == "BlockingService":
        from .services.blocking_service import BlockingService
        return BlockingService
    if name == "SimilarityService":
        from .services.similarity_service import SimilarityService
        return SimilarityService
    if name == "ClusteringService":
        from .services.clustering_service import ClusteringService
        return ClusteringService
    if name == "GoldenRecordService":
        from .services.golden_record_service import GoldenRecordService
        return GoldenRecordService
    if name == "GoldenRecordPersistenceService":
        from .services.golden_record_persistence_service import GoldenRecordPersistenceService
        return GoldenRecordPersistenceService
    if name == "BaseEntityResolutionService":
        from .services.base_service import BaseEntityResolutionService
        return BaseEntityResolutionService
    if name == "DataManager":
        from .data.data_manager import DataManager
        return DataManager

    # Strategies
    if name in [
        'BlockingStrategy', 'CollectBlockingStrategy', 'BM25BlockingStrategy',
        'HybridBlockingStrategy', 'GeographicBlockingStrategy',
        'GraphTraversalBlockingStrategy', 'VectorBlockingStrategy'
    ]:
        from . import strategies
        return getattr(strategies, name)

    # Enhanced services
    if name == "BatchSimilarityService":
        from .services.batch_similarity_service import BatchSimilarityService
        return BatchSimilarityService
    if name == "SimilarityEdgeService":
        from .services.similarity_edge_service import SimilarityEdgeService
        return SimilarityEdgeService
    if name == "WCCClusteringService":
        from .services.wcc_clustering_service import WCCClusteringService
        return WCCClusteringService
    if name == "AddressERService":
        from .services.address_er_service import AddressERService
        return AddressERService
    if name == "CrossCollectionMatchingService":
        from .services.cross_collection_matching_service import CrossCollectionMatchingService
        return CrossCollectionMatchingService
    if name == "EmbeddingService":
        from .services.embedding_service import EmbeddingService
        return EmbeddingService

    # Similarity components
    if name == "WeightedFieldSimilarity":
        from .similarity.weighted_field_similarity import WeightedFieldSimilarity
        return WeightedFieldSimilarity

    # Pipeline utilities
    if name in [
        'clean_er_results', 'count_inferred_edges',
        'validate_edge_quality', 'get_pipeline_statistics'
    ]:
        from .utils import pipeline_utils
        return getattr(pipeline_utils, name)

    # Configuration and utilities
    if name == "Config":
        from .utils.config import Config
        return Config
    if name in ['ERPipelineConfig', 'BlockingConfig', 'SimilarityConfig', 'ClusteringConfig']:
        from . import config
        return getattr(config, name)
    if name in ['DatabaseManager', 'get_database_manager', 'get_database']:
        from .utils import database
        return getattr(database, name)
    if name in ['DEFAULT_DATABASE_CONFIG', 'SIMILARITY_THRESHOLDS', 'ALGORITHM_WEIGHTS']:
        from .utils import constants
        return getattr(constants, name)

    # Demo capabilities
    if name in ['get_demo_manager', 'run_presentation_demo', 'run_automated_demo']:
        from . import demo
        return getattr(demo, name)

    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    # Core services
    'EntityResolver',
    'ConfigurableERPipeline',
    'BlockingService', 
    'SimilarityService',
    'ClusteringService',
    'GoldenRecordService',
    'GoldenRecordPersistenceService',
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
