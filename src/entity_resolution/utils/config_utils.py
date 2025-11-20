"""
Configuration Utilities

Provides utilities for environment variable verification and configuration
validation.
"""

import os
from typing import List, Tuple, Optional
from .logging import get_logger


def verify_arango_environment(
    required_vars: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """
    Verify required ArangoDB environment variables are set.
    
    Checks that all required environment variables are present and non-empty.
    Provides user-friendly error messages for missing variables.
    
    Args:
        required_vars: List of environment variable names to check.
            If None, uses defaults:
            - ARANGO_ENDPOINT
            - ARANGO_USER
            - ARANGO_PASSWORD
            - ARANGO_DATABASE
    
    Returns:
        Tuple of (is_valid: bool, missing_vars: List[str])
        - is_valid: True if all required variables are set, False otherwise
        - missing_vars: List of missing environment variable names
    """
    logger = get_logger(__name__)
    
    default_vars = ['ARANGO_ENDPOINT', 'ARANGO_USER', 'ARANGO_PASSWORD', 'ARANGO_DATABASE']
    required_vars = required_vars or default_vars
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.strip() == '':
            missing.append(var)
    
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        logger.info("Please configure your .env file or environment with:")
        for var in missing:
            logger.info(f"  {var}=your_value_here")
        return False, missing
    
    logger.debug(f"All required environment variables are set: {', '.join(required_vars)}")
    return True, []


def get_arango_config_from_env() -> Optional[dict]:
    """
    Get ArangoDB configuration from environment variables.
    
    Returns a dictionary with ArangoDB connection parameters from environment
    variables, or None if required variables are missing.
    
    Returns:
        Dictionary with keys: 'endpoint', 'username', 'password', 'database'
        Returns None if required variables are missing
    """
    logger = get_logger(__name__)
    
    is_valid, missing = verify_arango_environment()
    if not is_valid:
        return None
    
    config = {
        'endpoint': os.getenv('ARANGO_ENDPOINT'),
        'username': os.getenv('ARANGO_USER'),
        'password': os.getenv('ARANGO_PASSWORD'),
        'database': os.getenv('ARANGO_DATABASE')
    }
    
    # Optional variables
    if os.getenv('ARANGO_ROOT_PASSWORD'):
        config['root_password'] = os.getenv('ARANGO_ROOT_PASSWORD')
    
    return config

