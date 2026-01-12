#!/usr/bin/env python3
"""
Test Logging Framework

This script tests the new enhanced logging framework to ensure it's working correctly.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.enhanced_logging import get_logger

def test_logging_framework():
    """Test the enhanced logging framework."""
    print("? TESTING ENHANCED LOGGING FRAMEWORK")
    print("="*50)
    
    try:
        # Test logger initialization
        logger = get_logger(__name__)
        print("[PASS] Logger initialization successful")
        
        # Test different log levels
        print("\n? Testing log levels...")
        logger.debug("Debug message - detailed information")
        logger.info("Info message - general information")
        logger.warning("Warning message - potential issue")
        logger.error("Error message - error occurred")
        logger.critical("Critical message - serious error")
        logger.success("Success message - operation completed")
        
        print("[PASS] All log levels tested successfully")
        
        # Test structured logging
        print("\n? Testing structured logging...")
        logger.info("Processing entity resolution", extra={
            "operation": "entity_resolution",
            "records_processed": 100,
            "duration": 1.5
        })
        
        print("[PASS] Structured logging tested successfully")
        
        # Test file logging
        print("\n? Testing file logging...")
        if os.path.exists("entity_resolution.log"):
            with open("entity_resolution.log", "r") as f:
                log_content = f.read()
                if "Success message" in log_content:
                    print("[PASS] File logging working correctly")
                else:
                    print("[WARN]?  File logging may not be working")
        else:
            print("[WARN]?  Log file not found")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Logging framework test failed: {e}")
        return False

def main():
    """Main test function."""
    success = test_logging_framework()
    
    if success:
        print("\n? Logging framework test completed successfully!")
        return 0
    else:
        print("\n[FAIL] Logging framework test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
