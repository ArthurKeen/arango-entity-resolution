"""
Configuration Management for Entity Resolution System

Centralized configuration that can work with both Python and Foxx services.
"""

import os
import warnings
from typing import Dict, Any, Optional
from dataclasses import dataclass


class SecurityWarning(UserWarning):
    """Warning category for security-related issues"""
    pass


@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    host: str = "localhost"
    port: int = 8529
    username: str = "root"
    password: str = ""  # SECURITY: Must be provided via ARANGO_ROOT_PASSWORD environment variable
    database: str = "entity_resolution"
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """
        Create config from environment variables.
        
        Password is REQUIRED via ARANGO_ROOT_PASSWORD or ARANGO_PASSWORD environment variable.
        For local docker testing, USE_DEFAULT_PASSWORD=true can be set (development only).
        
        Raises:
            ValueError: If password is not provided and not in test mode
        """
        # Get password from environment (multiple sources for compatibility)
        password = os.getenv("ARANGO_PASSWORD") or os.getenv("ARANGO_ROOT_PASSWORD")
        
        # Fall back to default test password ONLY if explicitly set (docker local development)
        if not password:
            if os.getenv("USE_DEFAULT_PASSWORD") == "true":
                password = "testpassword123"  # Development/testing only
                warnings.warn(
                    "Using default test password. This is INSECURE and should only be "
                    "used for local docker development. Set ARANGO_ROOT_PASSWORD for production.",
                    UserWarning,  # Using UserWarning instead of SecurityWarning (not in standard library)
                    stacklevel=2
                )
            else:
                raise ValueError(
                    "Database password is required. Set one of:\n"
                    "  - ARANGO_ROOT_PASSWORD environment variable\n"
                    "  - ARANGO_PASSWORD environment variable\n"
                    "  - USE_DEFAULT_PASSWORD=true (local docker development only)"
                )
            
        return cls(
            host=os.getenv("ARANGO_HOST", cls.host),
            port=int(os.getenv("ARANGO_PORT", str(cls.port))),
            username=os.getenv("ARANGO_USERNAME", cls.username),
            password=password,
            database=os.getenv("ARANGO_DATABASE", cls.database)
        )


@dataclass
class EntityResolutionConfig:
    """Entity resolution algorithm configuration"""
    # Similarity and matching thresholds
    similarity_threshold: float = 0.8
    fallback_threshold: float = 0.5
    high_confidence_threshold: float = 0.9
    low_confidence_threshold: float = 0.6
    
    # Blocking and candidate generation
    max_candidates_per_record: int = 100
    max_batch_size: int = 1000
    blocking_threshold: float = 0.1
    
    # N-gram configuration
    ngram_length: int = 3
    ngram_min_length: int = 2
    ngram_max_length: int = 5
    
    # Clustering parameters
    max_cluster_size: int = 100
    min_cluster_size: int = 2
    cluster_density_threshold: float = 0.3
    quality_score_threshold: float = 0.6
    
    # Collection and view names
    default_collections: list = None
    default_source_collection: str = "customers"
    edge_collection: str = "similarities"
    cluster_collection: str = "entity_clusters"
    golden_record_collection: str = "golden_records"
    
    # Batch processing limits
    max_scored_pairs_batch: int = 10000
    max_target_docs_batch: int = 100
    
    # Field weights and importance
    default_field_importance: float = 1.0
    high_importance_multiplier: float = 1.2
    low_importance_multiplier: float = 0.7
    
    # Fellegi-Sunter framework defaults
    default_m_probability: float = 0.8
    default_u_probability: float = 0.05
    upper_threshold: float = 2.0
    lower_threshold: float = -1.0
    
    # Quality validation thresholds
    min_average_similarity: float = 0.7
    max_score_range: float = 0.5
    density_adequate_threshold: float = 0.3
    
    # Logging
    log_level: str = "INFO"
    enable_debug_logging: bool = False
    
    # Foxx service configuration
    foxx_mount_path: str = "/entity-resolution"
    foxx_timeout: int = 30
    enable_foxx_services: bool = True
    
    def __post_init__(self):
        if self.default_collections is None:
            self.default_collections = ['customers', 'entities', 'persons']


class Config:
    """Main configuration class that combines all configuration sections"""
    
    def __init__(self, 
                 db_config: Optional[DatabaseConfig] = None,
                 er_config: Optional[EntityResolutionConfig] = None):
        self.db = db_config or DatabaseConfig.from_env()
        self.er = er_config or EntityResolutionConfig()
        
    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables"""
        db_config = DatabaseConfig.from_env()
        er_config = EntityResolutionConfig()
        
        # Override ER config from environment
        if os.getenv("ER_SIMILARITY_THRESHOLD"):
            er_config.similarity_threshold = float(os.getenv("ER_SIMILARITY_THRESHOLD"))
        if os.getenv("ER_MAX_CANDIDATES"):
            er_config.max_candidates_per_record = int(os.getenv("ER_MAX_CANDIDATES"))
        if os.getenv("ER_NGRAM_LENGTH"):
            er_config.ngram_length = int(os.getenv("ER_NGRAM_LENGTH"))
        if os.getenv("ER_LOG_LEVEL"):
            er_config.log_level = os.getenv("ER_LOG_LEVEL")
        if os.getenv("ER_ENABLE_FOXX"):
            er_config.enable_foxx_services = os.getenv("ER_ENABLE_FOXX").lower() in ('true', '1', 'yes')
            
        return cls(db_config, er_config)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'database': {
                'host': self.db.host,
                'port': self.db.port,
                'username': self.db.username,
                'database': self.db.database,
                # Don't include password in dict representation
            },
            'entity_resolution': {
                'similarity_threshold': self.er.similarity_threshold,
                'max_candidates_per_record': self.er.max_candidates_per_record,
                'ngram_length': self.er.ngram_length,
                'max_cluster_size': self.er.max_cluster_size,
                'edge_collection': self.er.edge_collection,
                'cluster_collection': self.er.cluster_collection,
                'log_level': self.er.log_level,
                'enable_foxx_services': self.er.enable_foxx_services
            }
        }
    
    def get_foxx_service_url(self, endpoint: str = "") -> str:
        """Get URL for Foxx service endpoint"""
        base_url = f"http://{self.db.host}:{self.db.port}/_db/{self.db.database}{self.er.foxx_mount_path}"
        if endpoint:
            return f"{base_url}/{endpoint.lstrip('/')}"
        return base_url
    
    def get_database_url(self) -> str:
        """Get database connection URL"""
        return f"http://{self.db.host}:{self.db.port}"
    
    def get_auth_tuple(self) -> tuple:
        """Get authentication tuple for HTTP requests"""
        return (self.db.username, self.db.password)


# Global default configuration instance (lazy-loaded)
_default_config: Optional[Config] = None

def get_config() -> Config:
    """
    Get the default configuration instance.
    
    Lazily loads configuration on first access to avoid import-time errors.
    """
    global _default_config
    if _default_config is None:
        _default_config = Config.from_env()
    return _default_config

def set_config(config: Config):
    """Set the global configuration instance"""
    global _default_config
    _default_config = config
