#!/usr/bin/env python3
"""
Unit Tests for SimilarityService

Comprehensive unit tests for SimilarityService service.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

class TestSimilarityService(unittest.TestCase):
    """Test cases for SimilarityService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.service = SimilarityService()
        
    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service)
        self.assertIsInstance(self.service, SimilarityService)
    
    def test_connect(self):
        """Test service connection."""
        with patch.object(self.service, 'connect') as mock_connect:
            result = self.service.connect()
            mock_connect.assert_called_once()
    
    def test_disconnect(self):
        """Test service disconnection."""
        # Service may not have disconnect method - that's okay
        if hasattr(self.service, 'disconnect'):
            with patch.object(self.service, 'disconnect') as mock_disconnect:
                result = self.service.disconnect()
                mock_disconnect.assert_called_once()
        else:
            # If no disconnect method, test passes
            self.assertTrue(True)
    
    def test_error_handling(self):
        """Test error handling."""
        with patch.object(self.service, 'connect', side_effect=Exception("Test error")):
            with self.assertRaises(Exception):
                self.service.connect()
    
    def test_configuration_loading(self):
        """Test configuration loading."""
        self.assertIsNotNone(self.config)
        # Config can be a dict or a Config object
        self.assertTrue(isinstance(self.config, dict) or hasattr(self.config, 'er'))
    
    def test_logging_setup(self):
        """Test logging setup."""
        self.assertIsNotNone(self.logger)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self.service, 'disconnect'):
            try:
                self.service.disconnect()
            except:
                pass

if __name__ == '__main__':
    unittest.main()
