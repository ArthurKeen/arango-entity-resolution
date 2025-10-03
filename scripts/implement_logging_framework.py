#!/usr/bin/env python3
"""
Implement Logging Framework

This script replaces print statements with proper logging throughout the codebase.
"""

import sys
import os
import re
from typing import List, Tuple, Dict

class LoggingFrameworkImplementer:
    """Implements proper logging framework across the codebase."""
    
    def __init__(self):
        self.logging_patterns = {
            # Common print patterns to replace
            'print_success': r'print\(f?"✅\s*([^"]*)"\)',
            'print_error': r'print\(f?"❌\s*([^"]*)"\)',
            'print_warning': r'print\(f?"⚠️\s*([^"]*)"\)',
            'print_info': r'print\(f?"ℹ️\s*([^"]*)"\)',
            'print_debug': r'print\(f?"🔍\s*([^"]*)"\)',
            'print_generic': r'print\(([^)]+)\)'
        }
        
        self.logging_replacements = {
            'print_success': r'self.logger.success(r"\1")',
            'print_error': r'self.logger.error(r"\1")',
            'print_warning': r'self.logger.warning(r"\1")',
            'print_info': r'self.logger.info(r"\1")',
            'print_debug': r'self.logger.debug(r"\1")',
            'print_generic': r'self.logger.info(\1)'
        }
    
    def add_logging_import(self, content: str) -> str:
        """Add logging import if not present."""
        if 'from entity_resolution.utils.logging import get_logger' not in content:
            # Find the last import statement
            import_lines = []
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    import_lines.append(i)
            
            if import_lines:
                last_import_line = max(import_lines)
                lines.insert(last_import_line + 1, 'from entity_resolution.utils.logging import get_logger')
            else:
                # Add at the beginning
                lines.insert(0, 'from entity_resolution.utils.logging import get_logger')
            
            content = '\n'.join(lines)
        
        return content
    
    def add_logger_initialization(self, content: str) -> str:
        """Add logger initialization in __init__ method."""
        # Look for __init__ method
        if '__init__' in content and 'self.logger' not in content:
            # Add logger initialization
            init_pattern = r'(def __init__\(self[^:]*:\s*\n)'
            replacement = r'\1        self.logger = get_logger(__name__)\n'
            content = re.sub(init_pattern, replacement, content, flags=re.MULTILINE)
        
        return content
    
    def replace_print_statements(self, content: str) -> str:
        """Replace print statements with logging calls."""
        original_content = content
        
        # Replace specific print patterns
        for pattern_name, pattern in self.logging_patterns.items():
            if pattern_name in self.logging_replacements:
                replacement = self.logging_replacements[pattern_name]
                content = re.sub(pattern, replacement, content)
        
        return content
    
    def fix_file(self, file_path: str) -> bool:
        """Fix logging in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Add logging import
            content = self.add_logging_import(content)
            
            # Add logger initialization
            content = self.add_logger_initialization(content)
            
            # Replace print statements
            content = self.replace_print_statements(content)
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True
            
            return False
            
        except Exception as e:
            print(f"   ❌ Error fixing {file_path}: {e}")
            return False
    
    def fix_high_priority_files(self) -> int:
        """Fix logging in high-priority files with most print statements."""
        high_priority_files = [
            "scripts/setup_demo_database.py",
            "scripts/setup_test_database.py", 
            "scripts/crud/crud_operations.py",
            "scripts/database/manage_db.py",
            "scripts/realistic_integration_tests.py"
        ]
        
        fixes_applied = 0
        
        for file_path in high_priority_files:
            if os.path.exists(file_path):
                print(f"📄 Fixing {file_path}...")
                if self.fix_file(file_path):
                    print(f"   ✅ Applied logging framework")
                    fixes_applied += 1
                else:
                    print(f"   ℹ️  No changes needed")
            else:
                print(f"   ⚠️  File not found: {file_path}")
        
        return fixes_applied
    
    def create_logging_utility(self) -> None:
        """Create enhanced logging utility."""
        logging_util_content = '''#!/usr/bin/env python3
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
        'DEBUG': '\\033[36m',    # Cyan
        'INFO': '\\033[32m',     # Green
        'WARNING': '\\033[33m',  # Yellow
        'ERROR': '\\033[31m',    # Red
        'CRITICAL': '\\033[35m', # Magenta
        'SUCCESS': '\\033[32m',  # Green
        'RESET': '\\033[0m'      # Reset
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
'''
        
        with open('src/entity_resolution/utils/enhanced_logging.py', 'w') as f:
            f.write(logging_util_content)
        
        print("✅ Created enhanced logging utility")

def main():
    """Main function to implement logging framework."""
    print("🔧 IMPLEMENTING LOGGING FRAMEWORK")
    print("="*50)
    
    implementer = LoggingFrameworkImplementer()
    
    # Create enhanced logging utility
    implementer.create_logging_utility()
    
    # Fix high-priority files
    fixes_applied = implementer.fix_high_priority_files()
    
    print(f"\n📊 Summary: Applied logging framework to {fixes_applied} files")
    print("✅ Logging framework implementation completed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
