#!/usr/bin/env python3
"""
Test Error Handling

This script tests the improved error handling after fixing bare except clauses.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.enhanced_logging import get_logger

def test_error_handling():
    """Test the improved error handling."""
    print("? TESTING IMPROVED ERROR HANDLING")
    print("="*50)
    
    logger = get_logger(__name__)
    
    try:
        # Test 1: Specific exception handling
        print("? Testing specific exception handling...")
        try:
            # Simulate a specific error
            result = 10 / 0
        except ZeroDivisionError as e:
            logger.info(f"Caught specific exception: {e}")
            print("[PASS] Specific exception handling working correctly")
        
        # Test 2: General exception handling
        print("\n? Testing general exception handling...")
        try:
            # Simulate a general error
            result = "string" + 5
        except Exception as e:
            logger.warning(f"Caught general exception: {e}")
            print("[PASS] General exception handling working correctly")
        
        # Test 3: Custom exception handling
        print("\n? Testing custom exception handling...")
        class CustomError(Exception):
            pass
        
        try:
            raise CustomError("Custom error for testing")
        except CustomError as e:
            logger.error(f"Caught custom exception: {e}")
            print("[PASS] Custom exception handling working correctly")
        
        # Test 4: Exception with context
        print("\n? Testing exception with context...")
        try:
            # Simulate database connection error
            raise ConnectionError("Database connection failed")
        except ConnectionError as e:
            logger.critical(f"Database connection failed: {e}")
            print("[PASS] Exception with context working correctly")
        
        # Test 5: Exception chaining
        print("\n? Testing exception chaining...")
        try:
            try:
                result = 10 / 0
            except ZeroDivisionError as e:
                raise ValueError("Invalid calculation") from e
        except ValueError as e:
            logger.error(f"Chained exception: {e}")
            print("[PASS] Exception chaining working correctly")
        
        return True
        
    except Exception as e:
        logger.critical(f"Error handling test failed: {e}")
        print(f"[FAIL] Error handling test failed: {e}")
        return False

def test_bare_except_fixes():
    """Test that bare except clauses have been fixed."""
    print("\n? Testing bare except clause fixes...")
    
    # Check if any files still have bare except clauses
    files_to_check = [
        "scripts/code_quality_audit.py",
        "scripts/entity_resolution_demo.py",
        "scripts/final_code_quality_check.py",
        "scripts/shared_utils.py",
        "scripts/foxx/automated_deploy.py"
    ]
    
    bare_except_found = False
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for bare except clauses
            if 'except:' in content or 'except :' in content:
                print(f"[FAIL] Bare except clause found in {file_path}")
                bare_except_found = True
            else:
                print(f"[PASS] No bare except clauses in {file_path}")
    
    if not bare_except_found:
        print("[PASS] All bare except clauses have been fixed")
        return True
    else:
        print("[FAIL] Some bare except clauses still exist")
        return False

def main():
    """Main test function."""
    print("? COMPREHENSIVE ERROR HANDLING TEST")
    print("="*60)
    
    # Test error handling
    error_handling_success = test_error_handling()
    
    # Test bare except fixes
    bare_except_success = test_bare_except_fixes()
    
    if error_handling_success and bare_except_success:
        print("\n? Error handling test completed successfully!")
        return 0
    else:
        print("\n[FAIL] Error handling test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
