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
    BM25BlockingStrategy
)
from .services.batch_similarity_service import BatchSimilarityService
from .services.similarity_edge_service import SimilarityEdgeService
from .services.wcc_clustering_service import WCCClusteringService

# Configuration and utilities
from .utils.config import Config
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
    'BatchSimilarityService',
    'SimilarityEdgeService',
    'WCCClusteringService',
    
    # Configuration
    'Config',
    
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
