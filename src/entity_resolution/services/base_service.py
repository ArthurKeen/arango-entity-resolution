"""
Base Service Class for Entity Resolution Services

Provides common functionality for all entity resolution services:
- Configuration management
- Logging setup
- Database connectivity
- Error handling patterns

Note: v1.x legacy service. v2.0+ uses strategy pattern (see strategies/ directory).
"""

import requests
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from ..utils.config import Config, get_config
from ..utils.logging import get_logger
from ..utils.database import DatabaseMixin
from ..utils.constants import (
    FOXX_CONFIG, 
    ERROR_MESSAGES, 
    SUCCESS_MESSAGES,
    PERFORMANCE_LIMITS
)

# Re-export for convenience
__all__ = ['BaseEntityResolutionService', 'Config']


class BaseEntityResolutionService(DatabaseMixin, ABC):
    """
    Abstract base class for all entity resolution services
    
    Legacy v1.x service base class. v2.0+ uses strategy pattern.
    
    Provides common functionality:
    - Configuration initialization
    - Logging setup
    - Database connectivity (via DatabaseMixin)
    - Standard error handling patterns
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize base service with configuration and logging"""
        super().__init__()
        self.config = config or get_config()
        self.logger = get_logger(self.__class__.__name__)
        
    def connect(self) -> bool:
        """
        Test connection to database
        
        Returns:
            True if connected
        """
        # Test database connection
        if not self.test_connection():
            self.logger.error(ERROR_MESSAGES['database_connection'])
            return False
        
        self.logger.info(SUCCESS_MESSAGES['database_connected'])
        return True
    
    @abstractmethod
    def _get_service_name(self) -> str:
        """Return the name of this service for logging purposes"""
        pass
    
    def _handle_service_error(self, operation: str, error: Exception) -> Dict[str, Any]:
        """
        Standardized error handling for service operations
        
        Args:
            operation: Name of the operation that failed
            error: Exception that occurred
            
        Returns:
            Standardized error response
        """
        error_msg = f"{operation} failed: {str(error)}"
        self.logger.error(error_msg)
        
        return {
            "success": False,
            "error": error_msg,
            "operation": operation,
            "service": self._get_service_name()
        }
    
    def _validate_required_fields(self, data: Dict[str, Any], 
                                 required_fields: list) -> Optional[str]:
        """
        Validate that required fields are present in data
        
        Args:
            data: Data dictionary to validate
            required_fields: List of required field names
            
        Returns:
            None if valid, error message if invalid
        """
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            return f"Missing required fields: {missing_fields}"
        
        return None
