"""
Tests for config_utils module.
"""

import pytest
import os
from unittest.mock import patch, Mock

from entity_resolution.utils.config_utils import (
    verify_arango_environment,
    get_arango_config_from_env
)


class TestVerifyArangoEnvironment:
    """Tests for verify_arango_environment function."""
    
    @patch.dict(os.environ, {
        'ARANGO_HOST': 'localhost',
        'ARANGO_PORT': '8529',
        'ARANGO_USERNAME': 'test_user',
        'ARANGO_PASSWORD': 'test_password',
        'ARANGO_DATABASE': 'test_db'
    })
    def test_verify_arango_environment_all_present(self):
        """Test verification when all required variables are present."""
        is_valid, missing = verify_arango_environment()
        
        assert is_valid is True
        assert len(missing) == 0
    
    @patch.dict(os.environ, {
        'ARANGO_HOST': 'localhost',
        'ARANGO_PORT': '8529',
        'ARANGO_USERNAME': 'test_user',
        'ARANGO_PASSWORD': '',
        'ARANGO_DATABASE': 'test_db'
    }, clear=True)
    def test_verify_arango_environment_missing_password(self):
        """Test verification when password is empty."""
        is_valid, missing = verify_arango_environment()
        
        assert is_valid is False
        assert 'ARANGO_PASSWORD' in missing
    
    @patch.dict(os.environ, {}, clear=True)
    def test_verify_arango_environment_all_missing(self):
        """Test verification when all variables are missing."""
        is_valid, missing = verify_arango_environment()
        
        assert is_valid is False
        assert len(missing) == 5
        assert 'ARANGO_HOST' in missing
        assert 'ARANGO_PORT' in missing
        assert 'ARANGO_USERNAME' in missing
        assert 'ARANGO_PASSWORD' in missing
        assert 'ARANGO_DATABASE' in missing
    
    @patch.dict(os.environ, {
        'ARANGO_ENDPOINT': 'http://localhost:8529',
        'ARANGO_USER': 'test_user',
        'ARANGO_PASSWORD': 'test_password',
        'ARANGO_DATABASE': 'test_db'
    })
    def test_verify_arango_environment_custom_vars(self):
        """Test verification with custom variable list."""
        custom_vars = ['ARANGO_ENDPOINT', 'ARANGO_USER']
        is_valid, missing = verify_arango_environment(required_vars=custom_vars)
        
        assert is_valid is True
        assert len(missing) == 0
    
    @patch.dict(os.environ, {
        'ARANGO_ENDPOINT': 'http://localhost:8529'
    }, clear=True)
    def test_verify_arango_environment_custom_vars_missing(self):
        """Test verification with custom variables, some missing."""
        custom_vars = ['ARANGO_ENDPOINT', 'CUSTOM_VAR']
        is_valid, missing = verify_arango_environment(required_vars=custom_vars)
        
        assert is_valid is False
        assert 'CUSTOM_VAR' in missing
        assert 'ARANGO_ENDPOINT' not in missing


class TestGetArangoConfigFromEnv:
    """Tests for get_arango_config_from_env function."""
    
    @patch.dict(os.environ, {
        'ARANGO_HOST': 'localhost',
        'ARANGO_PORT': '8529',
        'ARANGO_USERNAME': 'test_user',
        'ARANGO_PASSWORD': 'test_password',
        'ARANGO_DATABASE': 'test_db'
    })
    def test_get_arango_config_from_env_all_present(self):
        """Test getting config when all variables are present."""
        config = get_arango_config_from_env()
        
        assert config is not None
        assert config['endpoint'] == 'http://localhost:8529'
        assert config['username'] == 'test_user'
        assert config['password'] == 'test_password'
        assert config['database'] == 'test_db'
    
    @patch.dict(os.environ, {
        'ARANGO_HOST': 'localhost',
        'ARANGO_PORT': '8529',
        'ARANGO_USERNAME': 'test_user',
        'ARANGO_PASSWORD': 'test_password',
        'ARANGO_DATABASE': 'test_db',
        'ARANGO_ROOT_PASSWORD': 'root_password'
    })
    def test_get_arango_config_from_env_with_root_password(self):
        """Test getting config with optional root password."""
        config = get_arango_config_from_env()
        
        assert config is not None
        assert config['root_password'] == 'root_password'
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_arango_config_from_env_missing_vars(self):
        """Test getting config when required variables are missing."""
        config = get_arango_config_from_env()
        
        assert config is None

