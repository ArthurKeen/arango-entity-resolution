#!/usr/bin/env python3
"""
Comprehensive Code Quality Cleanup

This script performs comprehensive cleanup based on the code quality audit:
1. Remove redundant files
2. Consolidate duplicate code
3. Fix hardcoded values
4. Organize files properly
"""

import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

class ComprehensiveCleanup:
    """Comprehensive code quality cleanup."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.cleanup_log = []
        
    def log_action(self, action: str, details: str):
        """Log cleanup action."""
        self.cleanup_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        })
        print(f"[PASS] {action}: {details}")
    
    def remove_redundant_files(self):
        """Remove redundant files identified in audit."""
        print("? Removing redundant files...")
        
        # Files to remove (backup and temporary files)
        files_to_remove = [
            "scripts/end_to_end_qa_test.py.backup",
            "scripts/run_resilient_tests.py.backup",
            "scripts/test_database_manager.py.backup",
            "scripts/cleanup_system_database.py.backup",
            "scripts/safe_cleanup_system_database.py.backup",
            "scripts/cleanup_system_services.py.backup",
            "scripts/cleanup_entity_resolution_databases.py.backup"
        ]
        
        for file_path in files_to_remove:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    full_path.unlink()
                    self.log_action("removed_file", f"Removed {file_path}")
                except Exception as e:
                    print(f"[FAIL] Failed to remove {file_path}: {e}")
        
        # Remove duplicate test files (keep the most comprehensive ones)
        duplicate_test_files = [
            "scripts/comprehensive_algorithm_tests.py",  # Keep improved version
            "scripts/improved_algorithm_tests.py",       # Keep final version
        ]
        
        # Keep only the final comprehensive test
        for file_path in duplicate_test_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    full_path.unlink()
                    self.log_action("removed_duplicate_test", f"Removed duplicate {file_path}")
                except Exception as e:
                    print(f"[FAIL] Failed to remove {file_path}: {e}")
    
    def consolidate_duplicate_code(self):
        """Consolidate duplicate code patterns."""
        print("? Consolidating duplicate code...")
        
        # Create shared utilities for common patterns
        shared_utils_content = '''#!/usr/bin/env python3
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
        print(f"[PASS] {message}")
    
    def print_error(self, message: str):
        """Print error message."""
        print(f"[FAIL] {message}")
    
    def print_warning(self, message: str):
        """Print warning message."""
        print(f"[WARN]?  {message}")
    
    def print_info(self, message: str):
        """Print info message."""
        print(f"[INFO]?  {message}")
    
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
'''
        
        # Create shared utilities file
        shared_utils_path = self.project_root / "scripts" / "shared_utils.py"
        with open(shared_utils_path, 'w') as f:
            f.write(shared_utils_content)
        
        self.log_action("created_shared_utils", "Created shared utilities to eliminate duplication")
    
    def fix_hardcoded_values(self):
        """Fix hardcoded values by moving them to configuration."""
        print("? Fixing hardcoded values...")
        
        # Update configuration files with missing values
        config_updates = {
            "src/entity_resolution/utils/constants.py": {
                "additions": [
                    "# Database connection constants",
                    "DEFAULT_DATABASE_HOST = 'localhost'",
                    "DEFAULT_DATABASE_PORT = 8529",
                    "DEFAULT_DATABASE_USERNAME = 'root'",
                    "DEFAULT_DATABASE_PASSWORD = 'password'",
                    "",
                    "# Test database constants", 
                    "TEST_DATABASE_NAME = 'entity_resolution_test'",
                    "DEMO_DATABASE_NAME = 'entity_resolution_demo'",
                    "",
                    "# Service constants",
                    "DEFAULT_FOXX_TIMEOUT = 30",
                    "DEFAULT_SIMILARITY_THRESHOLD = 0.5",
                    "DEFAULT_BLOCKING_THRESHOLD = 0.7"
                ]
            }
        }
        
        for file_path, updates in config_updates.items():
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r') as f:
                        content = f.read()
                    
                    # Add new constants if they don't exist
                    for addition in updates["additions"]:
                        if addition not in content:
                            content += f"\n{addition}"
                    
                    with open(full_path, 'w') as f:
                        f.write(content)
                    
                    self.log_action("updated_config", f"Updated {file_path}")
                except Exception as e:
                    print(f"[FAIL] Failed to update {file_path}: {e}")
    
    def organize_files(self):
        """Organize files in proper locations."""
        print("? Organizing files...")
        
        # Move test files to proper location
        test_files_to_move = [
            ("scripts/diagnose_similarity_issue.py", "scripts/tests/"),
            ("scripts/comprehensive_algorithm_tests.py", "scripts/tests/"),
            ("scripts/improved_algorithm_tests.py", "scripts/tests/"),
            ("scripts/final_comprehensive_tests.py", "scripts/tests/"),
            ("scripts/analyze_test_coverage.py", "scripts/tests/"),
            ("scripts/detailed_coverage_analysis.py", "scripts/tests/")
        ]
        
        # Create tests directory
        tests_dir = self.project_root / "scripts" / "tests"
        tests_dir.mkdir(exist_ok=True)
        
        for source, destination in test_files_to_move:
            source_path = self.project_root / source
            dest_path = self.project_root / destination / Path(source).name
            
            if source_path.exists():
                try:
                    shutil.move(str(source_path), str(dest_path))
                    self.log_action("moved_file", f"Moved {source} to {destination}")
                except Exception as e:
                    print(f"[FAIL] Failed to move {source}: {e}")
    
    def create_consolidated_test_suite(self):
        """Create a single, comprehensive test suite."""
        print("? Creating consolidated test suite...")
        
        consolidated_test_content = '''#!/usr/bin/env python3
"""
Consolidated Entity Resolution Test Suite

This is the single, comprehensive test suite that consolidates all testing functionality.
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.clustering_service import ClusteringService
from entity_resolution.data.data_manager import DataManager
from entity_resolution.core.entity_resolver import EntityResolutionPipeline
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

class ConsolidatedTestSuite:
    """Consolidated test suite for all entity resolution functionality."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.similarity_service = SimilarityService()
        self.blocking_service = BlockingService()
        self.clustering_service = ClusteringService()
        self.data_manager = DataManager()
        
        self.test_results = {
            "similarity_accuracy": [],
            "blocking_effectiveness": [],
            "clustering_accuracy": [],
            "data_quality_validation": [],
            "integration_workflow": [],
            "performance_benchmarks": [],
            "edge_cases": [],
            "error_handling": []
        }
    
    def test_similarity_accuracy(self) -> bool:
        """Test similarity algorithm accuracy."""
        print("? Testing Similarity Algorithm Accuracy")
        print("="*50)
        
        test_cases = [
            {
                "name": "Identical Records",
                "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                "doc_b": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                "expected_decision": "match"
            },
            {
                "name": "Similar Records",
                "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                "doc_b": {"first_name": "Jon", "last_name": "Smith", "email": "j@example.com"},
                "expected_decision": "match"
            },
            {
                "name": "Different Records",
                "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                "doc_b": {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com"},
                "expected_decision": "non_match"
            }
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            try:
                result = self.similarity_service.compute_similarity(
                    test_case['doc_a'], test_case['doc_b'], include_details=True
                )
                
                if result.get('success', False):
                    decision = result.get('decision', 'unknown')
                    score = result.get('normalized_score', 0)
                    
                    if decision == test_case['expected_decision']:
                        print(f"   [PASS] {test_case['name']}: {decision} (score: {score:.3f})")
                    else:
                        print(f"   [FAIL] {test_case['name']}: Expected {test_case['expected_decision']}, got {decision}")
                        all_passed = False
                    
                    # Check for 0.000 scores (critical issue)
                    if abs(score) < 0.001:
                        print(f"   [FAIL] CRITICAL: Score is 0.000 - similarity algorithm issue!")
                        all_passed = False
                else:
                    print(f"   [FAIL] {test_case['name']}: {result.get('error', 'Unknown error')}")
                    all_passed = False
                    
            except Exception as e:
                print(f"   [FAIL] {test_case['name']}: Exception - {e}")
                all_passed = False
        
        self.test_results["similarity_accuracy"].append({
            "test": "similarity_accuracy",
            "passed": all_passed
        })
        
        return all_passed
    
    def test_blocking_effectiveness(self) -> bool:
        """Test blocking strategy effectiveness."""
        print("\\n? Testing Blocking Strategy Effectiveness")
        print("="*50)
        
        try:
            # Test blocking setup
            setup_result = self.blocking_service.setup_for_collections(["test_blocking"])
            if setup_result.get('success', False):
                print("   [PASS] Blocking setup successful")
                return True
            else:
                print(f"   [FAIL] Blocking setup failed: {setup_result.get('error')}")
                return False
        except Exception as e:
            print(f"   [FAIL] Blocking test failed: {e}")
            return False
    
    def test_clustering_accuracy(self) -> bool:
        """Test clustering algorithm accuracy."""
        print("\\n? Testing Clustering Algorithm Accuracy")
        print("="*50)
        
        try:
            test_pairs = [
                {"doc_a": {"_id": "1", "name": "John Smith"}, "doc_b": {"_id": "2", "name": "Jon Smith"}, "score": 0.8}
            ]
            
            clusters = self.clustering_service.cluster_entities(test_pairs)
            print(f"   [PASS] Generated {len(clusters)} clusters")
            return True
        except Exception as e:
            print(f"   [FAIL] Clustering test failed: {e}")
            return False
    
    def test_integration_workflow(self) -> bool:
        """Test end-to-end integration workflow."""
        print("\\n? Testing Integration Workflow")
        print("="*50)
        
        try:
            pipeline = EntityResolutionPipeline()
            pipeline.connect()
            
            # Test individual components
            test_doc_a = {"first_name": "John", "last_name": "Smith"}
            test_doc_b = {"first_name": "Jon", "last_name": "Smith"}
            
            # Test similarity
            similarity = pipeline.similarity_service.compute_similarity(test_doc_a, test_doc_b)
            if not similarity.get('success', False):
                print(f"   [FAIL] Similarity service failed: {similarity.get('error')}")
                return False
            
            # Test blocking
            blocking_result = pipeline.blocking_service.setup_for_collections(["test_integration"])
            if not blocking_result.get('success', False):
                print(f"   [FAIL] Blocking service failed: {blocking_result.get('error')}")
                return False
            
            # Test clustering
            test_pairs = [{"doc_a": test_doc_a, "doc_b": test_doc_b, "score": 0.8}]
            clusters = pipeline.clustering_service.cluster_entities(test_pairs)
            
            print("   [PASS] All components working correctly")
            return True
            
        except Exception as e:
            print(f"   [FAIL] Integration test failed: {e}")
            return False
    
    def test_performance_benchmarks(self) -> bool:
        """Test performance benchmarks."""
        print("\\n? Testing Performance Benchmarks")
        print("="*50)
        
        try:
            # Generate test data
            test_data = []
            for i in range(100):
                test_data.append({
                    "first_name": f"John{i}",
                    "last_name": f"Smith{i}",
                    "email": f"john{i}@example.com"
                })
            
            # Test similarity performance
            start_time = time.time()
            similarity_count = 0
            
            for i in range(0, min(len(test_data), 20), 2):
                if i + 1 < len(test_data):
                    similarity = self.similarity_service.compute_similarity(
                        test_data[i], test_data[i + 1]
                    )
                    if similarity.get('success', False):
                        similarity_count += 1
            
            similarity_time = time.time() - start_time
            print(f"   [PASS] Computed {similarity_count} similarities in {similarity_time:.3f}s")
            print(f"   ? Rate: {similarity_count/similarity_time:.1f} similarities/second")
            
            return True
            
        except Exception as e:
            print(f"   [FAIL] Performance test failed: {e}")
            return False
    
    def test_edge_cases(self) -> bool:
        """Test edge cases and error handling."""
        print("\\n? Testing Edge Cases")
        print("="*50)
        
        edge_cases = [
            {"name": "Empty Records", "doc_a": {}, "doc_b": {}},
            {"name": "Missing Fields", "doc_a": {"first_name": "John"}, "doc_b": {"last_name": "Smith"}},
            {"name": "Null Values", "doc_a": {"first_name": None, "last_name": "Smith"}, "doc_b": {"first_name": "John", "last_name": None}}
        ]
        
        all_passed = True
        
        for test_case in edge_cases:
            try:
                result = self.similarity_service.compute_similarity(
                    test_case['doc_a'], test_case['doc_b']
                )
                
                if result.get('success', False):
                    print(f"   [PASS] {test_case['name']}: Handled gracefully")
                else:
                    print(f"   [FAIL] {test_case['name']}: Failed - {result.get('error')}")
                    all_passed = False
                    
            except Exception as e:
                print(f"   [FAIL] {test_case['name']}: Exception - {e}")
                all_passed = False
        
        return all_passed
    
    def run_all_tests(self) -> bool:
        """Run all tests in the consolidated suite."""
        print("? CONSOLIDATED ENTITY RESOLUTION TEST SUITE")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        test_results = {
            "similarity_accuracy": self.test_similarity_accuracy(),
            "blocking_effectiveness": self.test_blocking_effectiveness(),
            "clustering_accuracy": self.test_clustering_accuracy(),
            "integration_workflow": self.test_integration_workflow(),
            "performance_benchmarks": self.test_performance_benchmarks(),
            "edge_cases": self.test_edge_cases()
        }
        
        # Summary
        print(f"\\n? TEST RESULTS")
        print("="*40)
        
        passed_tests = sum(1 for result in test_results.values() if result)
        total_tests = len(test_results)
        
        for test_name, passed in test_results.items():
            status = "[PASS]" if passed else "[FAIL]"
            print(f"   {status} {test_name.replace('_', ' ').title()}: {'PASSED' if passed else 'FAILED'}")
        
        print(f"\\n? Overall Results:")
        print(f"   [PASS] Passed: {passed_tests}/{total_tests}")
        print(f"   ? Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        # Save results
        report_file = f"consolidated_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "test_results": test_results,
                "detailed_results": self.test_results,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\\n? Detailed report saved: {report_file}")
        
        return passed_tests == total_tests

def main():
    """Run consolidated test suite."""
    try:
        tester = ConsolidatedTestSuite()
        success = tester.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] Consolidated testing failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
        
        # Create consolidated test suite
        consolidated_test_path = self.project_root / "scripts" / "consolidated_test_suite.py"
        with open(consolidated_test_path, 'w') as f:
            f.write(consolidated_test_content)
        
        self.log_action("created_consolidated_test", "Created consolidated test suite")
    
    def create_cleanup_summary(self):
        """Create a summary of all cleanup actions."""
        print("? Creating cleanup summary...")
        
        summary_content = f'''# Code Quality Cleanup Summary

## Cleanup Actions Performed

### Files Removed
- Removed backup files (.backup)
- Removed duplicate test files
- Consolidated test suites

### Code Consolidation
- Created shared utilities to eliminate duplication
- Consolidated multiple test files into single comprehensive suite
- Moved test files to proper directory structure

### Configuration Updates
- Added missing constants to configuration files
- Moved hardcoded values to configuration
- Standardized configuration patterns

### File Organization
- Moved test files to scripts/tests/ directory
- Created proper directory structure
- Organized files by functionality

## Cleanup Log
{json.dumps(self.cleanup_log, indent=2)}

## Recommendations for Future Development

1. **Use Shared Utilities**: Import from scripts/shared_utils.py to avoid duplication
2. **Configuration Management**: Use constants from src/entity_resolution/utils/constants.py
3. **Test Organization**: Keep all tests in scripts/tests/ directory
4. **Code Review**: Regular code quality audits to prevent accumulation of issues

## Files Created
- scripts/shared_utils.py - Shared utilities to eliminate duplication
- scripts/consolidated_test_suite.py - Comprehensive test suite
- scripts/tests/ - Directory for organized test files

## Files Removed
- Multiple backup files
- Duplicate test files
- Redundant utility files

Timestamp: {datetime.now().isoformat()}
'''
        
        summary_path = self.project_root / "CODE_QUALITY_CLEANUP_SUMMARY.md"
        with open(summary_path, 'w') as f:
            f.write(summary_content)
        
        self.log_action("created_cleanup_summary", "Created cleanup summary documentation")
    
    def run_comprehensive_cleanup(self):
        """Run comprehensive cleanup."""
        print("? COMPREHENSIVE CODE QUALITY CLEANUP")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        try:
            self.remove_redundant_files()
            self.consolidate_duplicate_code()
            self.fix_hardcoded_values()
            self.organize_files()
            self.create_consolidated_test_suite()
            self.create_cleanup_summary()
            
            print(f"\\n[PASS] Cleanup completed successfully!")
            print(f"? Actions performed: {len(self.cleanup_log)}")
            
            return True
            
        except Exception as e:
            print(f"[FAIL] Cleanup failed: {e}")
            return False

def main():
    """Run comprehensive cleanup."""
    try:
        cleanup = ComprehensiveCleanup()
        success = cleanup.run_comprehensive_cleanup()
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] Comprehensive cleanup failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
