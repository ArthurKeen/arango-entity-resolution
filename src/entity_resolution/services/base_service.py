"""
Base Service Class for Entity Resolution Services

Provides common functionality for all entity resolution services:
- Configuration management
- Logging setup
- Database connectivity
- Foxx service connectivity
- Error handling patterns
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
    
    Provides common functionality:
    - Configuration initialization
    - Logging setup
    - Database connectivity (via DatabaseMixin)
    - Foxx service connectivity testing
    - Standard error handling patterns
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize base service with configuration and logging"""
        super().__init__()
        self.config = config or get_config()
        self.logger = get_logger(self.__class__.__name__)
        self.foxx_available = False
        
    def connect(self) -> bool:
        """
        Test connection to database and Foxx services if enabled
        
        Returns:
            True if connected or fallback mode available
        """
        # Test database connection first
        if not self.test_connection():
            self.logger.error(ERROR_MESSAGES['database_connection'])
            return False
        
        self.logger.info(SUCCESS_MESSAGES['database_connected'])
        
        # Test Foxx service connection if enabled
        if not self.config.er.enable_foxx_services:
            self.logger.info("Foxx services disabled, using Python fallback")
            return True
        
        try:
            # Test basic Foxx service availability
            health_url = self.config.get_foxx_service_url("health")
            timeout = FOXX_CONFIG['timeout_seconds']
            response = requests.get(health_url, auth=self.config.get_auth_tuple(), timeout=timeout)
            
            if response.status_code == 200:
                # Test service-specific endpoints
                service_available = self._test_service_endpoints()
                
                if service_available:
                    self.foxx_available = True
                    self.logger.info(f"Foxx {self._get_service_name()} service available")
                else:
                    self.logger.info(f"Foxx {self._get_service_name()} endpoints not implemented, using Python fallback")
            else:
                self.logger.warning("Foxx service not available, using Python fallback")
                
        except Exception as e:
            self.logger.warning(f"Cannot connect to Foxx services: {e}")
        
        return True
    
    @abstractmethod
    def _get_service_name(self) -> str:
        """Return the name of this service for logging purposes"""
        pass
    
    @abstractmethod
    def _test_service_endpoints(self) -> bool:
        """Test if service-specific Foxx endpoints are available"""
        pass
    
    def _make_foxx_request(self, endpoint: str, method: str = "GET", 
                          payload: Optional[Dict[str, Any]] = None,
                          timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Make a standardized request to Foxx service
        
        Args:
            endpoint: Foxx service endpoint (e.g., "similarity/compute")
            method: HTTP method (GET, POST, etc.)
            payload: Request payload for POST requests
            timeout: Request timeout
            
        Returns:
            Response data or error information
        """
        try:
            url = self.config.get_foxx_service_url(endpoint)
            timeout = timeout or FOXX_CONFIG['timeout_seconds']
            auth = self.config.get_auth_tuple()
            
            if method.upper() == "GET":
                response = requests.get(url, auth=auth, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, auth=auth, json=payload, timeout=timeout)
            else:
                return {"success": False, "error": f"Unsupported HTTP method: {method}"}
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Foxx service request timeout"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to Foxx service"}
        except Exception as e:
            return {"success": False, "error": f"Foxx request failed: {str(e)}"}
    
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
