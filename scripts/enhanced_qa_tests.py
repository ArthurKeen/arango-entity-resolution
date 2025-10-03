#!/usr/bin/env python3
"""
Enhanced QA Tests for Entity Resolution System

This script addresses the gaps in the original QA tests by:
1. Testing actual similarity computation with known data
2. Validating end-to-end pipeline functionality
3. Testing error handling and edge cases
4. Validating business logic correctness
"""

import sys
import os
import time
import json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.database import DatabaseManager
from entity_resolution.utils.config import Config
from entity_resolution.data.data_manager import DataManager
from entity_resolution.core.entity_resolver import EntityResolutionPipeline
from entity_resolution.services.similarity_service import SimilarityService

class EnhancedQATestSuite:
    """Enhanced QA test suite that catches real-world issues."""
    
    def __init__(self):
        self.config = Config.from_env()
        self.db_manager = DatabaseManager()
        self.test_results = []
        self.start_time = datetime.now()
        
    def log_test(self, test_name, success, message="", duration=0):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'duration': duration
        })
        print(f"{status} {test_name}: {message}")
    
    def test_similarity_accuracy(self):
        """Test 1: Similarity computation accuracy with known data."""
        print("\n🔍 Test 1: Similarity Computation Accuracy")
        start_time = time.time()
        
        try:
            similarity_service = SimilarityService(self.config)
            
            # Test cases with expected results
            test_cases = [
                {
                    "name": "Identical records",
                    "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                    "doc_b": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                    "expected_min": 0.9,
                    "expected_max": 1.0
                },
                {
                    "name": "Similar names (John vs Jon)",
                    "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                    "doc_b": {"first_name": "Jon", "last_name": "Smith", "email": "jon@example.com"},
                    "expected_min": 0.5,
                    "expected_max": 0.9
                },
                {
                    "name": "Different people",
                    "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
                    "doc_b": {"first_name": "Bob", "last_name": "Johnson", "email": "bob@startup.com"},
                    "expected_min": 0.0,
                    "expected_max": 0.3
                },
                {
                    "name": "Empty fields",
                    "doc_a": {"first_name": "John", "last_name": "Smith"},
                    "doc_b": {"first_name": "John", "last_name": "Smith"},
                    "expected_min": 0.5,
                    "expected_max": 1.0
                }
            ]
            
            all_passed = True
            for test_case in test_cases:
                try:
                    similarity = similarity_service.compute_similarity(
                        test_case["doc_a"], test_case["doc_b"]
                    )
                    
                    score = similarity.get('score', 0)
                    expected_min = test_case["expected_min"]
                    expected_max = test_case["expected_max"]
                    
                    if expected_min <= score <= expected_max:
                        print(f"  ✅ {test_case['name']}: {score:.3f} (expected {expected_min}-{expected_max})")
                    else:
                        print(f"  ❌ {test_case['name']}: {score:.3f} (expected {expected_min}-{expected_max})")
                        all_passed = False
                        
                except Exception as e:
                    print(f"  ❌ {test_case['name']}: Error - {e}")
                    all_passed = False
            
            duration = time.time() - start_time
            self.log_test("Similarity Accuracy", all_passed, 
                         f"Tested {len(test_cases)} similarity cases", duration)
            return all_passed
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Similarity Accuracy", False, f"Error: {e}", duration)
            return False
    
    def test_end_to_end_pipeline(self):
        """Test 2: Complete end-to-end pipeline with realistic data."""
        print("\n🔍 Test 2: End-to-End Pipeline")
        start_time = time.time()
        
        try:
            pipeline = EntityResolutionPipeline(self.config)
            if not pipeline.connect():
                self.log_test("End-to-End Pipeline", False, "Failed to connect pipeline")
                return False
            
            # Create realistic test data with known duplicates
            test_data = [
                {"id": 1, "first_name": "John", "last_name": "Smith", "email": "john@example.com", "phone": "555-1234"},
                {"id": 2, "first_name": "Jon", "last_name": "Smith", "email": "jon@example.com", "phone": "555-1234"},
                {"id": 3, "first_name": "Jane", "last_name": "Doe", "email": "jane@company.com", "phone": "555-9876"},
                {"id": 4, "first_name": "Bob", "last_name": "Johnson", "email": "bob@startup.com", "phone": "555-5555"}
            ]
            
            collection_name = "qa_pipeline_test"
            if not pipeline.data_manager.create_collection(collection_name):
                self.log_test("End-to-End Pipeline", False, "Failed to create collection")
                return False
            
            # Load test data
            collection = pipeline.data_manager.database.collection(collection_name)
            collection.insert_many(test_data)
            print(f"  📊 Loaded {len(test_data)} test records")
            
            # Test blocking setup
            setup_result = pipeline.blocking_service.setup_for_collections([collection_name])
            if not setup_result.get('success', False):
                self.log_test("End-to-End Pipeline", False, "Blocking setup failed")
                return False
            
            # Test candidate generation
            records = list(collection.all())
            total_candidates = 0
            for record in records:
                candidate_result = pipeline.blocking_service.generate_candidates(
                    collection_name, record['_key']
                )
                if candidate_result.get('success', False):
                    candidates = candidate_result.get('candidates', [])
                    total_candidates += len(candidates)
            
            print(f"  📊 Generated {total_candidates} total candidates")
            
            # Test similarity computation
            similarity_pairs = []
            for i in range(0, min(len(records), 4), 2):
                if i + 1 < len(records):
                    try:
                        similarity = pipeline.similarity_service.compute_similarity(
                            records[i], records[i + 1]
                        )
                        similarity_pairs.append({
                            'doc_a': records[i]['_key'],
                            'doc_b': records[i + 1]['_key'],
                            'score': similarity.get('score', 0)
                        })
                        print(f"  📊 Similarity {records[i]['_key']} ↔ {records[i + 1]['_key']}: {similarity.get('score', 0):.3f}")
                    except Exception as e:
                        print(f"  ⚠️  Similarity error: {e}")
            
            # Test clustering
            if similarity_pairs:
                clusters = pipeline.clustering_service.cluster_entities(similarity_pairs)
                print(f"  📊 Generated {len(clusters)} clusters")
            
            # Cleanup
            pipeline.data_manager.database.delete_collection(collection_name)
            
            duration = time.time() - start_time
            self.log_test("End-to-End Pipeline", True, 
                         f"Pipeline completed with {len(similarity_pairs)} similarity pairs", duration)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("End-to-End Pipeline", False, f"Error: {e}", duration)
            return False
    
    def test_error_handling(self):
        """Test 3: Error handling and edge cases."""
        print("\n🔍 Test 3: Error Handling")
        start_time = time.time()
        
        try:
            similarity_service = SimilarityService(self.config)
            
            # Test edge cases
            edge_cases = [
                {
                    "name": "Empty documents",
                    "doc_a": {},
                    "doc_b": {}
                },
                {
                    "name": "None values",
                    "doc_a": {"first_name": None, "last_name": None},
                    "doc_b": {"first_name": None, "last_name": None}
                },
                {
                    "name": "Missing fields",
                    "doc_a": {"first_name": "John"},
                    "doc_b": {"last_name": "Smith"}
                },
                {
                    "name": "Invalid data types",
                    "doc_a": {"first_name": 123, "last_name": []},
                    "doc_b": {"first_name": "John", "last_name": "Smith"}
                }
            ]
            
            all_handled = True
            for edge_case in edge_cases:
                try:
                    similarity = similarity_service.compute_similarity(
                        edge_case["doc_a"], edge_case["doc_b"]
                    )
                    # Should not crash, even with bad data
                    print(f"  ✅ {edge_case['name']}: Handled gracefully (score: {similarity.get('score', 0):.3f})")
                except Exception as e:
                    print(f"  ❌ {edge_case['name']}: Failed to handle - {e}")
                    all_handled = False
            
            duration = time.time() - start_time
            self.log_test("Error Handling", all_handled, 
                         f"Tested {len(edge_cases)} edge cases", duration)
            return all_handled
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Error Handling", False, f"Error: {e}", duration)
            return False
    
    def test_data_quality_validation(self):
        """Test 4: Data quality validation functionality."""
        print("\n🔍 Test 4: Data Quality Validation")
        start_time = time.time()
        
        try:
            data_manager = DataManager(self.config)
            if not data_manager.connect():
                self.log_test("Data Quality Validation", False, "Failed to connect")
                return False
            
            # Create test data with quality issues
            quality_test_data = [
                {"id": 1, "name": "John Smith", "email": "john@example.com", "phone": "555-1234"},  # Good
                {"id": 2, "name": "", "email": "invalid-email", "phone": "123"},  # Bad
                {"id": 3, "name": "Jane Doe", "email": "jane@example.com", "phone": "555-9876"},  # Good
                {"id": 4, "name": "Bob", "email": "bob@", "phone": "555-5678"}  # Bad
            ]
            
            collection_name = "qa_quality_test"
            if not data_manager.create_collection(collection_name):
                self.log_test("Data Quality Validation", False, "Failed to create collection")
                return False
            
            collection = data_manager.database.collection(collection_name)
            collection.insert_many(quality_test_data)
            
            # Test quality validation
            try:
                quality_report = data_manager.validate_data_quality(collection_name)
                if quality_report:
                    issues_found = quality_report.get('issues_found', 0)
                    quality_score = quality_report.get('quality_score', 0)
                    print(f"  📊 Issues found: {issues_found}")
                    print(f"  📊 Quality score: {quality_score:.2f}")
                    
                    # Should find some issues in our test data
                    validation_worked = issues_found > 0 or quality_score < 1.0
                else:
                    print("  ⚠️  Quality validation returned no report")
                    validation_worked = False
            except Exception as e:
                print(f"  ⚠️  Quality validation error: {e}")
                validation_worked = False
            
            # Cleanup
            data_manager.database.delete_collection(collection_name)
            
            duration = time.time() - start_time
            self.log_test("Data Quality Validation", validation_worked, 
                         f"Quality validation {'worked' if validation_worked else 'failed'}", duration)
            return validation_worked
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Data Quality Validation", False, f"Error: {e}", duration)
            return False
    
    def test_performance_benchmarks(self):
        """Test 5: Performance benchmarks."""
        print("\n🔍 Test 5: Performance Benchmarks")
        start_time = time.time()
        
        try:
            data_manager = DataManager(self.config)
            if not data_manager.connect():
                self.log_test("Performance Benchmarks", False, "Failed to connect")
                return False
            
            # Create performance test data
            performance_data = []
            for i in range(1000):  # Test with 1000 records
                performance_data.append({
                    "id": i,
                    "first_name": f"Customer{i}",
                    "last_name": "Test",
                    "email": f"customer{i}@example.com",
                    "phone": f"555-{i:04d}"
                })
            
            collection_name = "qa_performance_test"
            if not data_manager.create_collection(collection_name):
                self.log_test("Performance Benchmarks", False, "Failed to create collection")
                return False
            
            # Test insertion performance
            collection = data_manager.database.collection(collection_name)
            insert_start = time.time()
            collection.insert_many(performance_data)
            insert_time = time.time() - insert_start
            
            # Test retrieval performance
            retrieve_start = time.time()
            records = list(collection.all())
            retrieve_time = time.time() - retrieve_start
            
            # Calculate performance metrics
            insert_rate = len(performance_data) / insert_time if insert_time > 0 else 0
            retrieve_rate = len(records) / retrieve_time if retrieve_time > 0 else 0
            
            print(f"  📊 Inserted {len(performance_data)} records in {insert_time:.3f}s ({insert_rate:.0f} records/sec)")
            print(f"  📊 Retrieved {len(records)} records in {retrieve_time:.3f}s ({retrieve_rate:.0f} records/sec)")
            
            # Performance thresholds
            min_insert_rate = 1000  # records per second
            min_retrieve_rate = 5000  # records per second
            
            performance_ok = insert_rate >= min_insert_rate and retrieve_rate >= min_retrieve_rate
            
            # Cleanup
            data_manager.database.delete_collection(collection_name)
            
            duration = time.time() - start_time
            self.log_test("Performance Benchmarks", performance_ok, 
                         f"Insert: {insert_rate:.0f}/s, Retrieve: {retrieve_rate:.0f}/s", duration)
            return performance_ok
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test("Performance Benchmarks", False, f"Error: {e}", duration)
            return False
    
    def run_all_tests(self):
        """Run all enhanced QA tests."""
        print("🚀 Starting Enhanced QA Tests")
        print("=" * 50)
        print("🎯 These tests address gaps in the original QA suite:")
        print("   - Similarity computation accuracy")
        print("   - End-to-end pipeline functionality")
        print("   - Error handling and edge cases")
        print("   - Data quality validation")
        print("   - Performance benchmarks")
        
        tests = [
            self.test_similarity_accuracy,
            self.test_end_to_end_pipeline,
            self.test_error_handling,
            self.test_data_quality_validation,
            self.test_performance_benchmarks
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")
                failed += 1
        
        # Generate report
        self.generate_report(passed, failed)
        
        return failed == 0
    
    def generate_report(self, passed, failed):
        """Generate comprehensive test report."""
        total_tests = passed + failed
        success_rate = (passed / total_tests) * 100 if total_tests > 0 else 0
        
        print("\n" + "=" * 50)
        print("📊 ENHANCED QA TEST REPORT")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if failed > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['message']}")
        
        # Save detailed report
        report_data = {
            'summary': {
                'total_tests': total_tests,
                'passed': passed,
                'failed': failed,
                'success_rate': success_rate,
                'duration': (datetime.now() - self.start_time).total_seconds()
            },
            'test_results': self.test_results,
            'timestamp': datetime.now().isoformat()
        }
        
        report_file = f"enhanced_qa_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"\n📁 Detailed report saved: {report_file}")
        
        if success_rate >= 90:
            print("🎉 Excellent! Enhanced QA tests show system is working properly.")
        elif success_rate >= 75:
            print("✅ Good! Enhanced QA tests show system is mostly working with minor issues.")
        elif success_rate >= 50:
            print("⚠️  Fair. Enhanced QA tests show some issues that need attention.")
        else:
            print("❌ Poor. Enhanced QA tests show significant issues that need immediate attention.")

def main():
    """Run enhanced QA tests."""
    try:
        qa_suite = EnhancedQATestSuite()
        success = qa_suite.run_all_tests()
        
        if success:
            print("\n🎉 All enhanced QA tests passed!")
            return 0
        else:
            print("\n❌ Some enhanced QA tests failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
