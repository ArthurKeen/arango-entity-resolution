#!/usr/bin/env python3
"""
Enhanced Configuration Management

Centralized configuration management for the entity resolution system.
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "localhost"
    port: int = 8529
    username: str = "root"
    password: str = ""
    database_name: str = "entity_resolution"
    timeout: int = 30
    max_retries: int = 3

@dataclass
class ServiceConfig:
    """Service configuration."""
    blocking_service_url: str = "http://localhost:8529/_db/entity_resolution/blocking"
    similarity_service_url: str = "http://localhost:8529/_db/entity_resolution/similarity"
    clustering_service_url: str = "http://localhost:8529/_db/entity_resolution/clustering"
    timeout: int = 30
    max_retries: int = 3

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    file_path: str = "entity_resolution.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5

@dataclass
class PerformanceConfig:
    """Performance configuration."""
    max_workers: int = 4
    batch_size: int = 100
    cache_size: int = 10000
    cache_ttl: int = 3600

class EnhancedConfig:
    """Enhanced configuration management."""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        
        # Initialize configuration sections
        self.database = DatabaseConfig(**self.config.get('database', {}))
        self.service = ServiceConfig(**self.config.get('service', {}))
        self.logging = LoggingConfig(**self.config.get('logging', {}))
        self.performance = PerformanceConfig(**self.config.get('performance', {}))
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or environment."""
        config = {}
        
        # Try to load from config file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
        
        # Override with environment variables
        config.update(self._load_from_env())
        
        return config
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}
        
        # Database configuration
        if os.getenv('DB_HOST'):
            env_config['database'] = env_config.get('database', {})
            env_config['database']['host'] = os.getenv('DB_HOST')
        
        if os.getenv('DB_PORT'):
            env_config['database'] = env_config.get('database', {})
            env_config['database']['port'] = int(os.getenv('DB_PORT'))
        
        if os.getenv('DB_USERNAME'):
            env_config['database'] = env_config.get('database', {})
            env_config['database']['username'] = os.getenv('DB_USERNAME')
        
        if os.getenv('DB_PASSWORD'):
            env_config['database'] = env_config.get('database', {})
            env_config['database']['password'] = os.getenv('DB_PASSWORD')
        
        if os.getenv('DB_NAME'):
            env_config['database'] = env_config.get('database', {})
            env_config['database']['database_name'] = os.getenv('DB_NAME')
        
        # Service configuration
        if os.getenv('SERVICE_TIMEOUT'):
            env_config['service'] = env_config.get('service', {})
            env_config['service']['timeout'] = int(os.getenv('SERVICE_TIMEOUT'))
        
        # Logging configuration
        if os.getenv('LOG_LEVEL'):
            env_config['logging'] = env_config.get('logging', {})
            env_config['logging']['level'] = os.getenv('LOG_LEVEL')
        
        # Performance configuration
        if os.getenv('MAX_WORKERS'):
            env_config['performance'] = env_config.get('performance', {})
            env_config['performance']['max_workers'] = int(os.getenv('MAX_WORKERS'))
        
        return env_config
    
    def save_config(self) -> None:
        """Save configuration to file."""
        config_dict = {
            'database': {
                'host': self.database.host,
                'port': self.database.port,
                'username': self.database.username,
                'password': self.database.password,
                'database_name': self.database.database_name,
                'timeout': self.database.timeout,
                'max_retries': self.database.max_retries
            },
            'service': {
                'blocking_service_url': self.service.blocking_service_url,
                'similarity_service_url': self.service.similarity_service_url,
                'clustering_service_url': self.service.clustering_service_url,
                'timeout': self.service.timeout,
                'max_retries': self.service.max_retries
            },
            'logging': {
                'level': self.logging.level,
                'format': self.logging.format,
                'file_path': self.logging.file_path,
                'max_file_size': self.logging.max_file_size,
                'backup_count': self.logging.backup_count
            },
            'performance': {
                'max_workers': self.performance.max_workers,
                'batch_size': self.performance.batch_size,
                'cache_size': self.performance.cache_size,
                'cache_ttl': self.performance.cache_ttl
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_dict, f, indent=2)
    
    def get_database_url(self) -> str:
        """Get database URL."""
        return f"http://{self.database.host}:{self.database.port}"
    
    def get_service_url(self, service_name: str) -> str:
        """Get service URL."""
        service_urls = {
            'blocking': self.service.blocking_service_url,
            'similarity': self.service.similarity_service_url,
            'clustering': self.service.clustering_service_url
        }
        return service_urls.get(service_name, '')
    
    def validate_config(self) -> bool:
        """Validate configuration."""
        try:
            # Validate database configuration
            assert self.database.host, "Database host is required"
            assert self.database.port > 0, "Database port must be positive"
            assert self.database.username, "Database username is required"
            
            # Validate service configuration
            assert self.service.timeout > 0, "Service timeout must be positive"
            assert self.service.max_retries >= 0, "Service max retries must be non-negative"
            
            # Validate logging configuration
            assert self.logging.level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], "Invalid log level"
            
            # Validate performance configuration
            assert self.performance.max_workers > 0, "Max workers must be positive"
            assert self.performance.batch_size > 0, "Batch size must be positive"
            
            return True
            
        except AssertionError as e:
            print(f"Configuration validation failed: {e}")
            return False

def get_config() -> EnhancedConfig:
    """Get configuration instance."""
    return EnhancedConfig()

if __name__ == "__main__":
    # Test configuration
    config = get_config()
    print("Configuration loaded successfully")
    print(f"Database URL: {config.get_database_url()}")
    print(f"Service timeout: {config.service.timeout}")
    print(f"Log level: {config.logging.level}")
    print(f"Max workers: {config.performance.max_workers}")
