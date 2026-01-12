"""
Unit Tests for Configuration System

Comprehensive tests for config.py classes and functions.
"""

import pytest
import sys
import os
import warnings
from unittest.mock import patch, Mock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.config import (
    DatabaseConfig,
    EntityResolutionConfig,
    Config,
    get_config,
    set_config
)


class TestDatabaseConfig:
    """Test DatabaseConfig class."""
    
    def test_initialization_defaults(self):
        """Test initialization with defaults."""
        config = DatabaseConfig()
        
        assert config.host == "localhost"
        assert config.port == 8529
        assert config.username == "root"
        assert config.password == ""
        assert config.database == "entity_resolution"
    
    def test_initialization_custom_values(self):
        """Test initialization with custom values."""
        config = DatabaseConfig(
            host="example.com",
            port=9000,
            username="admin",
            password="secret",
            database="test_db"
        )
        
        assert config.host == "example.com"
        assert config.port == 9000
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.database == "test_db"
    
    @patch.dict(os.environ, {
        'ARANGO_HOST': 'testhost',
        'ARANGO_PORT': '9999',
        'ARANGO_USERNAME': 'testuser',
        'ARANGO_ROOT_PASSWORD': 'testpass',
        'ARANGO_DATABASE': 'testdb'
    }, clear=True)
    def test_from_env_all_variables(self):
        """Test from_env with all environment variables."""
        config = DatabaseConfig.from_env()
        
        assert config.host == "testhost"
        assert config.port == 9999
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.database == "testdb"
    
    @patch.dict(os.environ, {
        'ARANGO_ROOT_PASSWORD': 'testpass'
    }, clear=True)
    def test_from_env_with_password_only(self):
        """Test from_env with only password set."""
        config = DatabaseConfig.from_env()
        
        assert config.password == "testpass"
        assert config.host == "localhost"  # Default
        assert config.port == 8529  # Default
    
    @patch.dict(os.environ, {
        'ARANGO_PASSWORD': 'altpass'
    }, clear=True)
    def test_from_env_arango_password(self):
        """Test from_env with ARANGO_PASSWORD."""
        config = DatabaseConfig.from_env()
        
        assert config.password == "altpass"
    
    @patch.dict(os.environ, {
        'USE_DEFAULT_PASSWORD': 'true'
    }, clear=True)
    def test_from_env_default_password(self):
        """Test from_env with USE_DEFAULT_PASSWORD."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = DatabaseConfig.from_env()
            
            # Check that warning was issued
            assert len(w) > 0
            assert "default test password" in str(w[0].message).lower()
        
        assert config.password == "testpassword123"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_no_password_raises(self):
        """Test from_env raises error when no password."""
        with pytest.raises(ValueError, match="Database password is required"):
            DatabaseConfig.from_env()
    
    @patch.dict(os.environ, {
        'ARANGO_PORT': 'invalid'
    }, clear=True)
    def test_from_env_invalid_port(self):
        """Test from_env with invalid port."""
        # Should raise ValueError when converting to int
        with pytest.raises(ValueError):
            DatabaseConfig.from_env()


class TestEntityResolutionConfig:
    """Test EntityResolutionConfig class."""
    
    def test_initialization_defaults(self):
        """Test initialization with defaults."""
        config = EntityResolutionConfig()
        
        assert config.similarity_threshold == 0.8
        assert config.max_candidates_per_record == 100
        assert config.max_batch_size == 1000
        assert config.max_cluster_size == 100
        assert config.min_cluster_size == 2
        assert config.log_level == "INFO"
        assert config.enable_debug_logging is False
    
    def test_initialization_custom_values(self):
        """Test initialization with custom values."""
        config = EntityResolutionConfig(
            similarity_threshold=0.9,
            max_candidates_per_record=50,
            log_level="DEBUG"
        )
        
        assert config.similarity_threshold == 0.9
        assert config.max_candidates_per_record == 50
        assert config.log_level == "DEBUG"
    
    def test_post_init_default_collections(self):
        """Test __post_init__ sets default collections."""
        config = EntityResolutionConfig()
        
        assert config.default_collections == ['customers', 'entities', 'persons']
    
    def test_post_init_custom_collections(self):
        """Test __post_init__ with custom collections."""
        config = EntityResolutionConfig(default_collections=['custom'])
        
        assert config.default_collections == ['custom']


class TestConfig:
    """Test Config class."""
    
    def test_initialization_defaults(self):
        """Test initialization with defaults."""
        with patch('entity_resolution.utils.config.DatabaseConfig.from_env') as mock_from_env:
            mock_db_config = Mock()
            mock_from_env.return_value = mock_db_config
            
            config = Config()
            
            assert config.db == mock_db_config
            assert isinstance(config.er, EntityResolutionConfig)
            assert mock_from_env.called
    
    def test_initialization_custom_configs(self):
        """Test initialization with custom configs."""
        db_config = DatabaseConfig(host="custom")
        er_config = EntityResolutionConfig(similarity_threshold=0.9)
        
        config = Config(db_config=db_config, er_config=er_config)
        
        assert config.db == db_config
        assert config.er == er_config
        assert config.er.similarity_threshold == 0.9
    
    @patch.dict(os.environ, {
        'ER_SIMILARITY_THRESHOLD': '0.95',
        'ER_MAX_CANDIDATES': '200',
        'ER_NGRAM_LENGTH': '4',
        'ER_LOG_LEVEL': 'DEBUG',
        'ER_ENABLE_FOXX': 'false'
    })
    @patch('entity_resolution.utils.config.DatabaseConfig.from_env')
    def test_from_env_er_overrides(self, mock_db_from_env):
        """Test from_env with ER environment overrides."""
        mock_db_config = Mock()
        mock_db_from_env.return_value = mock_db_config
        
        config = Config.from_env()
        
        assert config.er.similarity_threshold == 0.95
        assert config.er.max_candidates_per_record == 200
        assert config.er.ngram_length == 4
        assert config.er.log_level == "DEBUG"
        assert config.er.enable_foxx_services is False
    
    @patch.dict(os.environ, {
        'ER_ENABLE_FOXX': '1'
    })
    @patch('entity_resolution.utils.config.DatabaseConfig.from_env')
    def test_from_env_foxx_enabled_variants(self, mock_db_from_env):
        """Test from_env with various FOXX enable values."""
        mock_db_config = Mock()
        mock_db_from_env.return_value = mock_db_config
        
        config = Config.from_env()
        assert config.er.enable_foxx_services is True
    
    def test_to_dict(self):
        """Test to_dict method."""
        db_config = DatabaseConfig(host="test", port=8529, username="root", database="testdb")
        er_config = EntityResolutionConfig(similarity_threshold=0.9)
        
        config = Config(db_config=db_config, er_config=er_config)
        result = config.to_dict()
        
        assert 'database' in result
        assert 'entity_resolution' in result
        assert result['database']['host'] == "test"
        assert result['database']['port'] == 8529
        assert 'password' not in result['database']  # Should not include password
        assert result['entity_resolution']['similarity_threshold'] == 0.9
    
    def test_get_foxx_service_url(self):
        """Test get_foxx_service_url method."""
        db_config = DatabaseConfig(host="localhost", port=8529, database="testdb")
        er_config = EntityResolutionConfig(foxx_mount_path="/er")
        config = Config(db_config=db_config, er_config=er_config)
        
        url = config.get_foxx_service_url()
        assert url == "http://localhost:8529/_db/testdb/er"
        
        url_with_endpoint = config.get_foxx_service_url("similarity")
        assert url_with_endpoint == "http://localhost:8529/_db/testdb/er/similarity"
        
        url_with_slash = config.get_foxx_service_url("/similarity")
        assert url_with_slash == "http://localhost:8529/_db/testdb/er/similarity"
    
    def test_get_database_url(self):
        """Test get_database_url method."""
        db_config = DatabaseConfig(host="example.com", port=9000)
        config = Config(db_config=db_config)
        
        url = config.get_database_url()
        assert url == "http://example.com:9000"
    
    def test_get_auth_tuple(self):
        """Test get_auth_tuple method."""
        db_config = DatabaseConfig(username="admin", password="secret")
        config = Config(db_config=db_config)
        
        auth = config.get_auth_tuple()
        assert auth == ("admin", "secret")


class TestConfigFunctions:
    """Test module-level functions."""
    
    @patch('entity_resolution.utils.config.Config.from_env')
    def test_get_config(self, mock_from_env):
        """Test get_config function."""
        mock_config = Mock()
        mock_from_env.return_value = mock_config
        
        # Reset global config
        import entity_resolution.utils.config as config_module
        config_module.default_config = None
        
        # This will call from_env
        config = get_config()
        
        # Should return the default config
        assert config is not None
    
    def test_set_config(self):
        """Test set_config function."""
        custom_config = Config(
            db_config=DatabaseConfig(host="custom"),
            er_config=EntityResolutionConfig()
        )
        
        set_config(custom_config)
        
        # Verify it was set
        config = get_config()
        assert config.db.host == "custom"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

