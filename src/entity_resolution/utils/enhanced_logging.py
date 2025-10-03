#!/usr/bin/env python3
"""
Enhanced Logging Utility

Provides consistent logging across the entity resolution system.
"""

import logging
import sys
from typing import Optional
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'SUCCESS': '\033[32m',  # Green
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_color = self.COLORS['RESET']
        
        # Add color to level name
        record.levelname = f"{log_color}{record.levelname}{reset_color}"
        
        return super().format(record)

class EntityResolutionLogger:
    """Enhanced logger for entity resolution system."""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup console and file handlers."""
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler('entity_resolution.log')
        file_handler.setLevel(logging.DEBUG)
        
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        self.logger.critical(message, *args, **kwargs)
    
    def success(self, message: str, *args, **kwargs):
        """Log success message."""
        # Create a custom log record for success
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, "", 0, message, args, None
        )
        record.levelname = "SUCCESS"
        self.logger.handle(record)

def get_logger(name: str, level: str = "INFO") -> EntityResolutionLogger:
    """Get logger instance."""
    return EntityResolutionLogger(name, level)

if __name__ == "__main__":
    # Test the logging utility
    logger = get_logger(__name__)
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.success("Success message")
