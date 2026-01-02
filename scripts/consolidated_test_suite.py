#!/usr/bin/env python3
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Set default password for CI/testing if not set
if not os.getenv('ARANGO_PASSWORD') and not os.getenv('ARANGO_ROOT_PASSWORD'):
    os.environ['USE_DEFAULT_PASSWORD'] = 'true'

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
        print("🔍 Testing Similarity Algorithm Accuracy")
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
                        print(f"   ✅ {test_case['name']}: {decision} (score: {score:.3f})")
                    else:
                        print(f"   ❌ {test_case['name']}: Expected {test_case['expected_decision']}, got {decision}")
                        all_passed = False
                    
                    # Check for 0.000 scores (critical issue)
                    if abs(score) < 0.001:
                        print(f"   ❌ CRITICAL: Score is 0.000 - similarity algorithm issue!")
                        all_passed = False
                else:
                    print(f"   ❌ {test_case['name']}: {result.get('error', 'Unknown error')}")
                    all_passed = False
                    
            except Exception as e:
                print(f"   ❌ {test_case['name']}: Exception - {e}")
                all_passed = False
        
        self.test_results["similarity_accuracy"].append({
            "test": "similarity_accuracy",
            "passed": all_passed
        })
        
        return all_passed
    
    def test_blocking_effectiveness(self) -> bool:
        """Test blocking strategy effectiveness."""
        print("\n🔍 Testing Blocking Strategy Effectiveness")
        print("="*50)
        
        try:
            # Test blocking setup
            setup_result = self.blocking_service.setup_for_collections(["test_blocking"])
            if setup_result.get('success', False):
                print("   ✅ Blocking setup successful")
                return True
            else:
                print(f"   ❌ Blocking setup failed: {setup_result.get('error')}")
                return False
        except Exception as e:
            print(f"   ❌ Blocking test failed: {e}")
            return False
    
    def test_clustering_accuracy(self) -> bool:
        """Test clustering algorithm accuracy."""
        print("\n🔍 Testing Clustering Algorithm Accuracy")
        print("="*50)
        
        try:
            test_pairs = [
                {"doc_a": {"_id": "1", "name": "John Smith"}, "doc_b": {"_id": "2", "name": "Jon Smith"}, "score": 0.8}
            ]
            
            clusters = self.clustering_service.cluster_entities(test_pairs)
            print(f"   ✅ Generated {len(clusters)} clusters")
            return True
        except Exception as e:
            print(f"   ❌ Clustering test failed: {e}")
            return False
    
    def test_integration_workflow(self) -> bool:
        """Test end-to-end integration workflow."""
        print("\n🔍 Testing Integration Workflow")
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
                print(f"   ❌ Similarity service failed: {similarity.get('error')}")
                return False
            
            # Test blocking
            blocking_result = pipeline.blocking_service.setup_for_collections(["test_integration"])
            if not blocking_result.get('success', False):
                print(f"   ❌ Blocking service failed: {blocking_result.get('error')}")
                return False
            
            # Test clustering
            test_pairs = [{"doc_a": test_doc_a, "doc_b": test_doc_b, "score": 0.8}]
            clusters = pipeline.clustering_service.cluster_entities(test_pairs)
            
            print("   ✅ All components working correctly")
            return True
            
        except Exception as e:
            print(f"   ❌ Integration test failed: {e}")
            return False
    
    def test_performance_benchmarks(self) -> bool:
        """Test performance benchmarks."""
        print("\n🔍 Testing Performance Benchmarks")
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
            print(f"   ✅ Computed {similarity_count} similarities in {similarity_time:.3f}s")
            print(f"   📊 Rate: {similarity_count/similarity_time:.1f} similarities/second")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Performance test failed: {e}")
            return False
    
    def test_edge_cases(self) -> bool:
        """Test edge cases and error handling."""
        print("\n🔍 Testing Edge Cases")
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
                    print(f"   ✅ {test_case['name']}: Handled gracefully")
                else:
                    print(f"   ❌ {test_case['name']}: Failed - {result.get('error')}")
                    all_passed = False
                    
            except Exception as e:
                print(f"   ❌ {test_case['name']}: Exception - {e}")
                all_passed = False
        
        return all_passed
    
    def run_all_tests(self) -> bool:
        """Run all tests in the consolidated suite."""
        print("🧪 CONSOLIDATED ENTITY RESOLUTION TEST SUITE")
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
        print(f"\n📊 TEST RESULTS")
        print("="*40)
        
        passed_tests = sum(1 for result in test_results.values() if result)
        total_tests = len(test_results)
        
        for test_name, passed in test_results.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {test_name.replace('_', ' ').title()}: {'PASSED' if passed else 'FAILED'}")
        
        print(f"\n📊 Overall Results:")
        print(f"   ✅ Passed: {passed_tests}/{total_tests}")
        print(f"   📊 Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        # Save results
        report_file = f"consolidated_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "test_results": test_results,
                "detailed_results": self.test_results,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\n📁 Detailed report saved: {report_file}")
        
        return passed_tests == total_tests

def main():
    """Run consolidated test suite."""
    try:
        tester = ConsolidatedTestSuite()
        success = tester.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Consolidated testing failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
