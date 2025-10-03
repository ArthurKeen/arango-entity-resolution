#!/usr/bin/env python3
"""
Resilient Test Runner

Runs all entity resolution tests with resilient database management.
This script ensures that tests can run reliably even when:
- Port 8529 is occupied by other services
- ArangoDB containers are not running
- Database/collections don't exist
- Test data is missing

Usage:
    python scripts/run_resilient_tests.py [test_name]
    
Examples:
    python scripts/run_resilient_tests.py                    # Run all tests
    python scripts/run_resilient_tests.py similarity          # Run similarity tests
    python scripts/run_resilient_tests.py blocking            # Run blocking tests
    python scripts/run_resilient_tests.py clustering          # Run clustering tests
    python scripts/run_resilient_tests.py complete            # Run complete pipeline test
"""

import sys
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional


class ResilientTestRunner:
    """Runs tests with resilient database management"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.scripts_dir = self.project_root / "scripts"
        self.examples_dir = self.project_root / "examples"
        
        # Available tests
        self.available_tests = {
            "similarity": "test_similarity_service_resilient.py",
            "blocking": "test_blocking_service.py", 
            "clustering": "test_clustering_service.py",
            "complete": "complete_entity_resolution_demo.py"
        }
        
        self.test_results = {}
    
    def setup_test_database(self) -> bool:
        """Setup test database with resilience"""
        print("🔧 Setting up test database...")
        
        setup_script = self.scripts_dir / "setup_test_database.py"
        if not setup_script.exists():
            print(f"❌ Test database setup script not found: {setup_script}")
            return False
        
        try:
            result = subprocess.run(
                [sys.executable, str(setup_script)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            if result.returncode == 0:
                print("✅ Test database setup completed successfully")
                return True
            else:
                print(f"❌ Test database setup failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error running test database setup: {e}")
            return False
    
    def run_single_test(self, test_name: str, test_file: str) -> Dict[str, Any]:
        """Run a single test with resilient database management"""
        print(f"\n🧪 Running {test_name} test...")
        print("-" * 50)
        
        test_path = self.examples_dir / test_file
        if not test_path.exists():
            return {
                "test_name": test_name,
                "success": False,
                "error": f"Test file not found: {test_path}",
                "duration": 0
            }
        
        start_time = time.time()
        
        try:
            # Run the test
            result = subprocess.run(
                [sys.executable, str(test_path)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                print(f"✅ {test_name} test passed ({duration:.2f}s)")
                return {
                    "test_name": test_name,
                    "success": True,
                    "output": result.stdout,
                    "duration": duration
                }
            else:
                print(f"❌ {test_name} test failed ({duration:.2f}s)")
                print(f"Error: {result.stderr}")
                return {
                    "test_name": test_name,
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout,
                    "duration": duration
                }
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ {test_name} test error: {e}")
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "duration": duration
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all available tests"""
        print("🚀 Running all entity resolution tests...")
        print("=" * 60)
        
        # Setup test database first
        if not self.setup_test_database():
            print("❌ Failed to setup test database, aborting tests")
            return {"success": False, "error": "Database setup failed"}
        
        # Run each test
        results = {}
        total_tests = len(self.available_tests)
        passed_tests = 0
        
        for test_name, test_file in self.available_tests.items():
            result = self.run_single_test(test_name, test_file)
            results[test_name] = result
            
            if result["success"]:
                passed_tests += 1
        
        # Summary
        print(f"\n📊 TEST SUMMARY")
        print("=" * 30)
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
        
        return {
            "success": passed_tests == total_tests,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "results": results
        }
    
    def run_specific_test(self, test_name: str) -> Dict[str, Any]:
        """Run a specific test"""
        if test_name not in self.available_tests:
            print(f"❌ Unknown test: {test_name}")
            print(f"Available tests: {', '.join(self.available_tests.keys())}")
            return {"success": False, "error": f"Unknown test: {test_name}"}
        
        print(f"🎯 Running specific test: {test_name}")
        print("=" * 40)
        
        # Setup test database first
        if not self.setup_test_database():
            print("❌ Failed to setup test database, aborting test")
            return {"success": False, "error": "Database setup failed"}
        
        # Run the specific test
        test_file = self.available_tests[test_name]
        result = self.run_single_test(test_name, test_file)
        
        return {
            "success": result["success"],
            "test_name": test_name,
            "result": result
        }
    
    def check_test_environment(self) -> bool:
        """Check if test environment is ready"""
        print("🔍 Checking test environment...")
        
        # Check if required files exist
        required_files = [
            self.scripts_dir / "setup_test_database.py",
            self.scripts_dir / "test_database_manager.py",
            self.examples_dir / "test_similarity_service_resilient.py"
        ]
        
        for file_path in required_files:
            if not file_path.exists():
                print(f"❌ Required file missing: {file_path}")
                return False
        
        print("✅ Test environment is ready")
        return True


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run entity resolution tests with resilient database management")
    parser.add_argument("test_name", nargs="?", help="Specific test to run (similarity, blocking, clustering, complete)")
    parser.add_argument("--check", action="store_true", help="Check test environment only")
    
    args = parser.parse_args()
    
    runner = ResilientTestRunner()
    
    # Check environment if requested
    if args.check:
        if runner.check_test_environment():
            print("✅ Test environment is ready")
            sys.exit(0)
        else:
            print("❌ Test environment issues detected")
            sys.exit(1)
    
    # Run tests
    if args.test_name:
        # Run specific test
        result = runner.run_specific_test(args.test_name)
        if result["success"]:
            print(f"\n🎉 {args.test_name} test completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ {args.test_name} test failed!")
            sys.exit(1)
    else:
        # Run all tests
        result = runner.run_all_tests()
        if result["success"]:
            print(f"\n🎉 All tests completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Some tests failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
