#!/usr/bin/env python3
"""
Shared Utilities for Entity Resolution System

Common utilities to eliminate code duplication.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

class SharedUtilities:
    """Shared utilities to eliminate code duplication."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
    
    def print_success(self, message: str):
        """Print success message."""
        print(f"✅ {message}")
    
    def print_error(self, message: str):
        """Print error message."""
        print(f"❌ {message}")
    
    def print_warning(self, message: str):
        """Print warning message."""
        print(f"⚠️  {message}")
    
    def print_info(self, message: str):
        """Print info message."""
        print(f"ℹ️  {message}")
    
    def run_command(self, command: str, capture_output: bool = True) -> Dict[str, Any]:
        """Run a command and return results."""
        import subprocess
        try:
            if capture_output:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            else:
                result = subprocess.run(command, shell=True)
                return {
                    "success": result.returncode == 0,
                    "returncode": result.returncode
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "returncode": -1
            }
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return {
            "host": self.config.arangodb.host,
            "port": self.config.arangodb.port,
            "username": self.config.arangodb.username,
            "password": self.config.arangodb.password,
            "database": self.config.arangodb.db_name
        }
    
    def validate_environment(self) -> bool:
        """Validate environment setup."""
        try:
            # Check if ArangoDB is running
            config = self.get_database_config()
            import requests
            response = requests.get(f"http://{config['host']}:{config['port']}")
            return response.status_code == 200
        except:
            return False

# Global instance for easy access
shared_utils = SharedUtilities()
