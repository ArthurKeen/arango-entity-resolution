#!/usr/bin/env python3
"""
Comprehensive Test Runner

Runs all unit tests and generates coverage report.
"""

import sys
import os
import unittest
import subprocess
from pathlib import Path

def run_all_tests():
    """Run all unit tests."""
    print("🧪 RUNNING COMPREHENSIVE UNIT TESTS")
    print("="*50)
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n📊 TEST SUMMARY")
    print("="*30)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    return result.wasSuccessful()

def run_coverage_analysis():
    """Run coverage analysis."""
    print("\n📊 RUNNING COVERAGE ANALYSIS")
    print("="*40)
    
    try:
        # Run coverage
        result = subprocess.run([
            'python', '-m', 'coverage', 'run', '-m', 'unittest', 'discover', 'tests'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Generate coverage report
            subprocess.run(['python', '-m', 'coverage', 'report'], check=True)
            subprocess.run(['python', '-m', 'coverage', 'html'], check=True)
            print("✅ Coverage report generated: htmlcov/index.html")
        else:
            print(f"❌ Coverage analysis failed: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Coverage analysis error: {e}")
    except FileNotFoundError:
        print("⚠️  Coverage module not found. Install with: pip install coverage")

def main():
    """Main test runner function."""
    # Run tests
    success = run_all_tests()
    
    # Run coverage analysis
    run_coverage_analysis()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
