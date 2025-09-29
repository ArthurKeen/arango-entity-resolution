"""
Unified Database Connection Management

Centralizes all ArangoDB connection logic to eliminate duplication
and provide consistent connection handling across the codebase.
"""

import os
from typing import Optional, Dict, Any, Tuple
from arango import ArangoClient
from arango.exceptions import ArangoError

from .config import Config, get_config
from .logging import get_logger


class DatabaseManager:
    """
    Centralized ArangoDB connection manager
    
    Eliminates duplicate connection code throughout the codebase
    and provides consistent error handling and configuration.
    """
    
    _instance = None
    _client = None
    _databases = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.config = get_config()
            self.logger = get_logger(__name__)
            self._client = None
            self._databases = {}
            self.initialized = True
    
    @property
    def client(self) -> ArangoClient:
        """Get ArangoDB client, creating if needed"""
        if self._client is None:
            hosts = f"http://{self.config.db.host}:{self.config.db.port}"
            self._client = ArangoClient(hosts=hosts)
        return self._client
    
    def get_database(self, database_name: Optional[str] = None):
        """
        Get database connection with caching
        
        Args:
            database_name: Database name (uses config default if None)
            
        Returns:
            Database connection
            
        Raises:
            ArangoError: If connection fails
        """
        db_name = database_name or self.config.db.database
        
        if db_name not in self._databases:
            try:
                db = self.client.db(
                    db_name,
                    username=self.config.db.username,
                    password=self.config.db.password
                )
                # Test connection
                db.properties()
                self._databases[db_name] = db
                self.logger.debug(f"Connected to database: {db_name}")
            except Exception as e:
                self.logger.error(f"Failed to connect to database {db_name}: {e}")
                raise ArangoError(f"Database connection failed: {e}")
        
        return self._databases[db_name]
    
    def test_connection(self, database_name: Optional[str] = None) -> bool:
        """
        Test database connection
        
        Args:
            database_name: Database to test (uses config default if None)
            
        Returns:
            True if connection successful
        """
        try:
            db = self.get_database(database_name)
            db.properties()
            return True
        except Exception:
            return False
    
    def create_database_if_not_exists(self, database_name: str) -> bool:
        """
        Create database if it doesn't exist
        
        Args:
            database_name: Name of database to create
            
        Returns:
            True if created or already exists
        """
        try:
            system_db = self.get_database('_system')
            
            if not system_db.has_database(database_name):
                system_db.create_database(database_name)
                self.logger.info(f"Created database: {database_name}")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to create database {database_name}: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for debugging"""
        return {
            "host": self.config.db.host,
            "port": self.config.db.port,
            "database": self.config.db.database,
            "username": self.config.db.username,
            "url": f"http://{self.config.db.host}:{self.config.db.port}"
        }
    
    def close_connections(self):
        """Close all cached database connections"""
        self._databases.clear()
        if self._client:
            self._client.close()
            self._client = None


# Convenience functions for backward compatibility
def get_database_manager() -> DatabaseManager:
    """Get the singleton database manager instance"""
    return DatabaseManager()


def get_database(database_name: Optional[str] = None):
    """Get database connection (convenience function)"""
    return get_database_manager().get_database(database_name)


def test_database_connection(database_name: Optional[str] = None) -> bool:
    """Test database connection (convenience function)"""
    return get_database_manager().test_connection(database_name)


def get_connection_args() -> Dict[str, Any]:
    """Get connection arguments from configuration"""
    config = get_config()
    return {
        'host': config.db.host,
        'port': config.db.port,
        'username': config.db.username,
        'password': config.db.password,
        'database': config.db.database
    }


class DatabaseMixin:
    """
    Mixin class for objects that need database access
    
    Provides consistent database connection without duplication
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_manager = None
        self._database = None
    
    @property
    def db_manager(self) -> DatabaseManager:
        """Get database manager instance"""
        if self._db_manager is None:
            self._db_manager = get_database_manager()
        return self._db_manager
    
    @property
    def database(self):
        """Get database connection"""
        if self._database is None:
            self._database = self.db_manager.get_database()
        return self._database
    
    def test_connection(self) -> bool:
        """Test database connectivity"""
        return self.db_manager.test_connection()
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return self.db_manager.get_connection_info()


# Legacy compatibility - will be deprecated
class ArangoBaseConnection(DatabaseMixin):
    """
    Legacy base connection class
    
    DEPRECATED: Use DatabaseManager or DatabaseMixin instead
    """
    
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None,
                 username: Optional[str] = None, password: Optional[str] = None):
        # Issue deprecation warning
        import warnings
        warnings.warn(
            "ArangoBaseConnection is deprecated. Use DatabaseManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        super().__init__()
        
        # Override config if parameters provided
        if any(param is not None for param in [host, port, username, password]):
            config = get_config()
            if host: config.db.host = host
            if port: config.db.port = port
            if username: config.db.username = username
            if password: config.db.password = password
    
    def print_success(self, message: str) -> None:
        """Print success message with checkmark"""
        print(f"✓ {message}")
    
    def print_warning(self, message: str) -> None:
        """Print warning message with warning symbol"""
        print(f"⚠ {message}")
    
    def print_error(self, message: str) -> None:
        """Print error message with X symbol"""
        print(f"✗ {message}")
    
    def print_info(self, message: str) -> None:
        """Print info message with icon"""
        print(f"📋 {message}")


def get_default_connection_args() -> Dict[str, Any]:
    """
    Get default connection arguments
    
    DEPRECATED: Use get_connection_args() instead
    """
    import warnings
    warnings.warn(
        "get_default_connection_args is deprecated. Use get_connection_args instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_connection_args()
