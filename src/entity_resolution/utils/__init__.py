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
- View utilities (view_utils.py) - ArangoSearch view verification and fixing
- Pipeline utilities (pipeline_utils.py) - ER pipeline state management
- Configuration utilities (config_utils.py) - Environment verification
- Validation utilities (validation_utils.py) - ER result validation
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
from .view_utils import (
    resolve_analyzer_name,
    verify_view_analyzers,
    fix_view_analyzer_names,
    verify_and_fix_view_analyzers
)
from .pipeline_utils import clean_er_results
from .config_utils import (
    verify_arango_environment,
    get_arango_config_from_env
)
from .validation_utils import validate_er_results

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
    
    # View utilities
    'resolve_analyzer_name',
    'verify_view_analyzers',
    'fix_view_analyzer_names',
    'verify_and_fix_view_analyzers',
    
    # Pipeline utilities
    'clean_er_results',
    
    # Configuration utilities
    'verify_arango_environment',
    'get_arango_config_from_env',
    
    # Validation utilities
    'validate_er_results',
]
