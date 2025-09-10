"""
Logging utilities for Entity Resolution System
"""

import logging
import sys
from typing import Optional
from .config import get_config


def setup_logging(log_level: Optional[str] = None, 
                 enable_debug: Optional[bool] = None) -> logging.Logger:
    """
    Set up logging for the entity resolution system
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_debug: Whether to enable debug logging
        
    Returns:
        Configured logger instance
    """
    config = get_config()
    
    # Use provided parameters or fall back to config
    level = log_level or config.er.log_level
    debug = enable_debug if enable_debug is not None else config.er.enable_debug_logging
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger('entity_resolution')
    logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    if debug:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'entity_resolution') -> logging.Logger:
    """
    Get a logger instance for a specific module
    
    Args:
        name: Logger name (usually module name)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Initialize default logger
default_logger = setup_logging()
