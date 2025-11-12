"""
Utility modules for entity resolution.

This package contains various utilities used throughout the entity resolution system:
- Configuration management (config.py)
- Database connection utilities (database.py)
- Logging configuration (logging.py)
- Algorithm implementations (algorithms.py)
- Constants and defaults (constants.py)
- Input validation (validation.py)
- Graph utilities (graph_utils.py)
"""

from .config import Config, get_config, DatabaseConfig, EntityResolutionConfig
from .database import get_database, DatabaseManager, get_database_manager
from .logging import get_logger
from .constants import *
from .validation import (
    validate_collection_name,
    validate_field_name,
    validate_field_names,
    validate_view_name,
    validate_database_name
)
from .graph_utils import (
    format_vertex_id,
    extract_key_from_vertex_id,
    parse_vertex_id,
    normalize_vertex_ids
)

__all__ = [
    # Configuration
    'Config',
    'get_config',
    'DatabaseConfig',
    'EntityResolutionConfig',
    
    # Database
    'get_database',
    'DatabaseManager',
    'get_database_manager',
    
    # Logging
    'get_logger',
    
    # Validation
    'validate_collection_name',
    'validate_field_name',
    'validate_field_names',
    'validate_view_name',
    'validate_database_name',
    
    # Graph utilities
    'format_vertex_id',
    'extract_key_from_vertex_id',
    'parse_vertex_id',
    'normalize_vertex_ids',
]
