"""
Entity Resolution System for ArangoDB

A complete entity resolution system that combines:
- Python orchestration and data processing
- ArangoDB native storage and querying
- Foxx microservices for high-performance operations
- Graph-based clustering algorithms

Main components:
- EntityResolver: Main orchestration class
- BlockingService: Record blocking and candidate generation
- SimilarityService: Fellegi-Sunter similarity computation
- ClusteringService: Graph-based entity clustering
- DataManager: Data ingestion and management
"""

__version__ = "1.0.0"
__author__ = "Entity Resolution Team"

from .core.entity_resolver import EntityResolver
from .services.blocking_service import BlockingService
from .services.similarity_service import SimilarityService
from .services.clustering_service import ClusteringService
from .services.golden_record_service import GoldenRecordService
from .data.data_manager import DataManager
from .utils.config import Config

__all__ = [
    'EntityResolver',
    'BlockingService', 
    'SimilarityService',
    'ClusteringService',
    'GoldenRecordService',
    'DataManager',
    'Config'
]
