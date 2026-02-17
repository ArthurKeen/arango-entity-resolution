"""
Configuration Utilities

Provides utilities for environment variable verification and configuration
validation.
"""

import os
from typing import List, Tuple, Optional
from .logging import get_logger


_ALIASES = {
    # Canonical -> aliases
    "ARANGO_HOST": ["ARANGO_DB_HOST"],
    "ARANGO_PORT": ["ARANGO_DB_PORT"],
    "ARANGO_USERNAME": ["ARANGO_USER", "ARANGO_ROOT_USERNAME"],
    "ARANGO_PASSWORD": ["ARANGO_ROOT_PASSWORD"],
    "ARANGO_DATABASE": ["TEST_DB_NAME"],
}


def _is_set(var_name: str) -> bool:
    value = os.getenv(var_name)
    if value and value.strip() != "":
        return True
    for alias in _ALIASES.get(var_name, []):
        alias_value = os.getenv(alias)
        if alias_value and alias_value.strip() != "":
            return True

    # Back-compat: ARANGO_ENDPOINT can supply host/port.
    if var_name in ("ARANGO_HOST", "ARANGO_PORT"):
        endpoint = os.getenv("ARANGO_ENDPOINT")
        if endpoint and endpoint.strip() != "":
            return True

    # Back-compat: ARANGO_ENDPOINT is satisfied by ARANGO_HOST/ARANGO_PORT.
    if var_name == "ARANGO_ENDPOINT":
        endpoint = os.getenv("ARANGO_ENDPOINT")
        if endpoint and endpoint.strip() != "":
            return True
        return _is_set("ARANGO_HOST") and _is_set("ARANGO_PORT")

    # Back-compat: ARANGO_USER is satisfied by ARANGO_USERNAME.
    if var_name == "ARANGO_USER":
        return _is_set("ARANGO_USERNAME")

    return False


def _get_first(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value and value.strip() != "":
            return value
    return None


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
    
    # Canonical env vars (preferred). We also accept aliases for backwards compatibility.
    default_vars = ['ARANGO_HOST', 'ARANGO_PORT', 'ARANGO_USERNAME', 'ARANGO_PASSWORD', 'ARANGO_DATABASE']
    required_vars = required_vars or default_vars
    
    missing = []
    for var in required_vars:
        if not _is_set(var):
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
    
    endpoint = _get_first("ARANGO_ENDPOINT")
    host = _get_first("ARANGO_HOST", "ARANGO_DB_HOST") or "localhost"
    port = _get_first("ARANGO_PORT", "ARANGO_DB_PORT") or "8529"
    if not endpoint:
        endpoint = f"http://{host}:{port}"

    config = {
        'endpoint': endpoint,
        'username': _get_first('ARANGO_USERNAME', 'ARANGO_USER', 'ARANGO_ROOT_USERNAME'),
        'password': _get_first('ARANGO_PASSWORD', 'ARANGO_ROOT_PASSWORD'),
        'database': _get_first('ARANGO_DATABASE', 'TEST_DB_NAME')
    }
    
    # Optional variables
    if os.getenv('ARANGO_ROOT_PASSWORD'):
        config['root_password'] = os.getenv('ARANGO_ROOT_PASSWORD')
    
    return config

