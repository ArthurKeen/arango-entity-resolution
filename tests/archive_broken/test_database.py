"""
Unit Tests for Database Management

Comprehensive tests for database.py classes and functions.
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, call
from arango.exceptions import ArangoError

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.database import (
    DatabaseManager,
    DatabaseMixin,
    get_database_manager,
    get_database,
    test_database_connection,
    get_connection_args,
    ArangoBaseConnection
)


class TestDatabaseManager:
    """Test DatabaseManager class."""
    
    def test_singleton_pattern(self):
        """Test that DatabaseManager is a singleton."""
        manager1 = DatabaseManager()
        manager2 = DatabaseManager()
        
        assert manager1 is manager2
    
    @patch('entity_resolution.utils.database.get_config')
    @patch('entity_resolution.utils.database.get_logger')
    def test_initialization(self, mock_get_logger, mock_get_config):
        """Test DatabaseManager initialization."""
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        manager = DatabaseManager()
        
        assert manager.config == mock_config
        assert manager.logger == mock_logger
        assert manager._client is None
        assert manager._databases == {}
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_client_property(self, mock_get_config, mock_client_class):
        """Test client property creation."""
        mock_config = Mock()
        mock_config.db.host = "localhost"
        mock_config.db.port = 8529
        mock_get_config.return_value = mock_config
        
        manager = DatabaseManager()
        client = manager.client
        
        assert client is not None
        mock_client_class.assert_called_once_with(hosts="http://localhost:8529")
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_get_database(self, mock_get_config, mock_client_class):
        """Test get_database method."""
        mock_config = Mock()
        mock_config.db.database = "testdb"
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_db = Mock()
        mock_db.properties.return_value = {}
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        db = manager.get_database()
        
        assert db == mock_db
        mock_client.db.assert_called_once_with(
            "testdb",
            username="root",
            password="pass"
        )
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_get_database_caching(self, mock_get_config, mock_client_class):
        """Test that database connections are cached."""
        mock_config = Mock()
        mock_config.db.database = "testdb"
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_db = Mock()
        mock_db.properties.return_value = {}
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        db1 = manager.get_database()
        db2 = manager.get_database()
        
        assert db1 is db2
        assert mock_client.db.call_count == 1  # Only called once
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_get_database_custom_name(self, mock_get_config, mock_client_class):
        """Test get_database with custom database name."""
        mock_config = Mock()
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_db = Mock()
        mock_db.properties.return_value = {}
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        db = manager.get_database("customdb")
        
        mock_client.db.assert_called_once_with(
            "customdb",
            username="root",
            password="pass"
        )
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_get_database_connection_error(self, mock_get_config, mock_client_class):
        """Test get_database raises error on connection failure."""
        mock_config = Mock()
        mock_config.db.database = "testdb"
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_db = Mock()
        mock_db.properties.side_effect = Exception("Connection failed")
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        
        with pytest.raises(ArangoError, match="Database connection failed"):
            manager.get_database()
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_test_connection_success(self, mock_get_config, mock_client_class):
        """Test test_connection returns True on success."""
        mock_config = Mock()
        mock_config.db.database = "testdb"
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_db = Mock()
        mock_db.properties.return_value = {}
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        result = manager.test_connection()
        
        assert result is True
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_test_connection_failure(self, mock_get_config, mock_client_class):
        """Test test_connection returns False on failure."""
        mock_config = Mock()
        mock_config.db.database = "testdb"
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_db = Mock()
        mock_db.properties.side_effect = Exception("Connection failed")
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        result = manager.test_connection()
        
        assert result is False
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_create_database_if_not_exists_new(self, mock_get_config, mock_client_class):
        """Test create_database_if_not_exists creates new database."""
        mock_config = Mock()
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_system_db = Mock()
        mock_system_db.has_database.return_value = False
        mock_system_db.create_database.return_value = None
        mock_client.db.return_value = mock_system_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        result = manager.create_database_if_not_exists("newdb")
        
        assert result is True
        mock_system_db.create_database.assert_called_once_with("newdb")
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_create_database_if_not_exists_existing(self, mock_get_config, mock_client_class):
        """Test create_database_if_not_exists with existing database."""
        mock_config = Mock()
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_system_db = Mock()
        mock_system_db.has_database.return_value = True
        mock_client.db.return_value = mock_system_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        result = manager.create_database_if_not_exists("existingdb")
        
        assert result is True
        mock_system_db.create_database.assert_not_called()
    
    @patch('entity_resolution.utils.database.get_config')
    def test_get_connection_info(self, mock_get_config):
        """Test get_connection_info method."""
        mock_config = Mock()
        mock_config.db.host = "localhost"
        mock_config.db.port = 8529
        mock_config.db.database = "testdb"
        mock_config.db.username = "root"
        mock_get_config.return_value = mock_config
        
        manager = DatabaseManager()
        info = manager.get_connection_info()
        
        assert info['host'] == "localhost"
        assert info['port'] == 8529
        assert info['database'] == "testdb"
        assert info['username'] == "root"
        assert info['url'] == "http://localhost:8529"
    
    @patch('entity_resolution.utils.database.ArangoClient')
    @patch('entity_resolution.utils.database.get_config')
    def test_close_connections(self, mock_get_config, mock_client_class):
        """Test close_connections method."""
        mock_config = Mock()
        mock_config.db.database = "testdb"
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_get_config.return_value = mock_config
        
        mock_client = Mock()
        mock_db = Mock()
        mock_db.properties.return_value = {}
        mock_client.db.return_value = mock_db
        mock_client_class.return_value = mock_client
        
        manager = DatabaseManager()
        manager.get_database()  # Create a connection
        manager.close_connections()
        
        assert manager._databases == {}
        mock_client.close.assert_called_once()


class TestDatabaseMixin:
    """Test DatabaseMixin class."""
    
    class TestClass(DatabaseMixin):
        """Test class using DatabaseMixin."""
        def __init__(self):
            super().__init__()
    
    @patch('entity_resolution.utils.database.get_database_manager')
    def test_db_manager_property(self, mock_get_manager):
        """Test db_manager property."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        obj = self.TestClass()
        manager = obj.db_manager
        
        assert manager == mock_manager
        assert obj._db_manager == mock_manager
    
    @patch('entity_resolution.utils.database.get_database_manager')
    def test_database_property(self, mock_get_manager):
        """Test database property."""
        mock_manager = Mock()
        mock_db = Mock()
        mock_manager.get_database.return_value = mock_db
        mock_get_manager.return_value = mock_manager
        
        obj = self.TestClass()
        db = obj.database
        
        assert db == mock_db
        mock_manager.get_database.assert_called_once()
    
    @patch('entity_resolution.utils.database.get_database_manager')
    def test_test_connection(self, mock_get_manager):
        """Test test_connection method."""
        mock_manager = Mock()
        mock_manager.test_connection.return_value = True
        mock_get_manager.return_value = mock_manager
        
        obj = self.TestClass()
        result = obj.test_connection()
        
        assert result is True
        mock_manager.test_connection.assert_called_once()
    
    @patch('entity_resolution.utils.database.get_database_manager')
    def test_get_connection_info(self, mock_get_manager):
        """Test get_connection_info method."""
        mock_manager = Mock()
        mock_manager.get_connection_info.return_value = {"host": "localhost"}
        mock_get_manager.return_value = mock_manager
        
        obj = self.TestClass()
        info = obj.get_connection_info()
        
        assert info == {"host": "localhost"}
        mock_manager.get_connection_info.assert_called_once()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @patch('entity_resolution.utils.database.DatabaseManager')
    def test_get_database_manager(self, mock_manager_class):
        """Test get_database_manager function."""
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        
        from entity_resolution.utils.database import get_database_manager
        result = get_database_manager()
        
        assert result == mock_manager
    
    @patch('entity_resolution.utils.database.get_database_manager')
    def test_get_database_function(self, mock_get_manager):
        """Test get_database convenience function."""
        mock_manager = Mock()
        mock_db = Mock()
        mock_manager.get_database.return_value = mock_db
        mock_get_manager.return_value = mock_manager
        
        db = get_database("testdb")
        
        assert db == mock_db
        mock_manager.get_database.assert_called_once_with("testdb")
    
    @patch('entity_resolution.utils.database.get_database_manager')
    def test_test_database_connection_function(self, mock_get_manager):
        """Test test_database_connection convenience function."""
        mock_manager = Mock()
        mock_manager.test_connection.return_value = True
        mock_get_manager.return_value = mock_manager
        
        result = test_database_connection("testdb")
        
        assert result is True
        mock_manager.test_connection.assert_called_once_with("testdb")
    
    @patch('entity_resolution.utils.database.get_config')
    def test_get_connection_args(self, mock_get_config):
        """Test get_connection_args function."""
        mock_config = Mock()
        mock_config.db.host = "localhost"
        mock_config.db.port = 8529
        mock_config.db.username = "root"
        mock_config.db.password = "pass"
        mock_config.db.database = "testdb"
        mock_get_config.return_value = mock_config
        
        args = get_connection_args()
        
        assert args['host'] == "localhost"
        assert args['port'] == 8529
        assert args['username'] == "root"
        assert args['password'] == "pass"
        assert args['database'] == "testdb"


class TestArangoBaseConnection:
    """Test ArangoBaseConnection (legacy class)."""
    
    @patch('entity_resolution.utils.database.get_config')
    def test_deprecation_warning(self, mock_get_config):
        """Test that ArangoBaseConnection issues deprecation warning."""
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        with pytest.warns(DeprecationWarning, match="ArangoBaseConnection is deprecated"):
            conn = ArangoBaseConnection()
        
        assert conn is not None
    
    @patch('entity_resolution.utils.database.get_config')
    def test_override_config(self, mock_get_config):
        """Test that ArangoBaseConnection can override config."""
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        with pytest.warns(DeprecationWarning):
            conn = ArangoBaseConnection(host="custom", port=9000)
        
        assert mock_config.db.host == "custom"
        assert mock_config.db.port == 9000
    
    @patch('entity_resolution.utils.database.get_config')
    def test_print_methods(self, mock_get_config):
        """Test print helper methods."""
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        with pytest.warns(DeprecationWarning):
            conn = ArangoBaseConnection()
        
        # Test print methods (they just print, so we can't easily test output)
        conn.print_success("test")
        conn.print_warning("test")
        conn.print_error("test")
        conn.print_info("test")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

