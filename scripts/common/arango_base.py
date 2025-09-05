#!/usr/bin/env python3
"""
Base ArangoDB Connection and Utilities
Shared functionality for database management and CRUD operations
"""

import os
from typing import Optional, Dict, Any
from arango import ArangoClient


class ArangoBaseConnection:
    """Base class for ArangoDB connections with common functionality"""
    
    def __init__(self, host: str = "localhost", port: int = 8529, 
                 username: str = "root", password: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        # Use environment variable or default password
        self.password = password or os.getenv('ARANGO_ROOT_PASSWORD', 'testpassword123')
        self.client = ArangoClient(hosts=f"http://{host}:{port}")
        
    def test_connection(self, database: str = '_system') -> bool:
        """Test connection to ArangoDB"""
        try:
            db = self.client.db(database, username=self.username, password=self.password)
            db.properties()
            return True
        except Exception:
            return False
    
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
    """Get default connection arguments from environment variables"""
    return {
        'host': os.getenv('ARANGO_HOST', 'localhost'),
        'port': int(os.getenv('ARANGO_PORT', '8529')),
        'username': os.getenv('ARANGO_USERNAME', 'root'),
        'password': os.getenv('ARANGO_ROOT_PASSWORD', 'testpassword123')
    }


def add_common_args(parser) -> None:
    """Add common ArangoDB connection arguments to argument parser"""
    defaults = get_default_connection_args()
    
    parser.add_argument('--host', default=defaults['host'], 
                       help='ArangoDB host')
    parser.add_argument('--port', type=int, default=defaults['port'], 
                       help='ArangoDB port')
    parser.add_argument('--username', '-u', default=defaults['username'], 
                       help='Username')
    parser.add_argument('--password', '-p', default=defaults['password'], 
                       help='Password')
