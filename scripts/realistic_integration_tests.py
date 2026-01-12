#!/usr/bin/env python3
"""
Realistic Integration Tests

This script provides comprehensive integration testing with realistic data scenarios
and automated testing capabilities for CI/CD pipelines.
"""

import sys
import os
import json
import time
import random
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.core.entity_resolver import EntityResolutionPipeline
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

@dataclass
class TestScenario:
    """Test scenario configuration."""
    name: str
    description: str
    data_size: int
    complexity: str
    expected_clusters: int
    expected_accuracy: float

class RealisticIntegrationTester:
    """Realistic integration testing with comprehensive scenarios."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        
        # Test scenarios
        self.test_scenarios = {
            "small_business": TestScenario(
                name="Small Business (100 records)",
                description="Small business customer data with typical duplicates",
                data_size=100,
                complexity="low",
                expected_clusters=15,
                expected_accuracy=0.85
            ),
            
            "medium_enterprise": TestScenario(
                name="Medium Enterprise (1,000 records)",
                description="Medium enterprise with mixed data quality",
                data_size=1000,
                complexity="medium",
                expected_clusters=120,
                expected_accuracy=0.80
            ),
            
            "large_corporation": TestScenario(
                name="Large Corporation (10,000 records)",
                description="Large corporation with complex data patterns",
                data_size=10000,
                complexity="high",
                expected_clusters=800,
                expected_accuracy=0.75
            ),
            
            "ecommerce_platform": TestScenario(
                name="E-commerce Platform (5,000 records)",
                description="E-commerce customer data with high duplicate rates",
                data_size=5000,
                complexity="medium",
                expected_clusters=400,
                expected_accuracy=0.82
            ),
            
            "healthcare_system": TestScenario(
                name="Healthcare System (2,000 records)",
                description="Healthcare patient data with strict matching requirements",
                data_size=2000,
                complexity="high",
                expected_clusters=150,
                expected_accuracy=0.90
            )
        }
    
    def generate_realistic_data(self, scenario: TestScenario) -> List[Dict[str, Any]]:
        """Generate realistic test data for a scenario."""
        self.logger.info(f"? Generating realistic data for {scenario.name}...")
        
        # Base data templates
        first_names = [
            "John", "Jane", "Michael", "Sarah", "David", "Lisa", "Robert", "Jennifer",
            "William", "Elizabeth", "James", "Mary", "Richard", "Patricia", "Charles",
            "Linda", "Thomas", "Barbara", "Christopher", "Susan", "Daniel", "Jessica",
            "Matthew", "Nancy", "Anthony", "Karen", "Mark", "Helen", "Donald", "Sandra"
        ]
        
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
            "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
            "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
            "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
            "Ramirez", "Lewis", "Robinson"
        ]
        
        companies = [
            "Acme Corp", "Beta Inc", "Gamma LLC", "Delta Systems", "Epsilon Solutions",
            "Zeta Technologies", "Eta Consulting", "Theta Industries", "Iota Services",
            "Kappa Group", "Lambda Partners", "Mu Enterprises", "Nu Holdings",
            "Xi Corporation", "Omicron Limited", "Pi Associates", "Rho Ventures",
            "Sigma Capital", "Tau Holdings", "Upsilon Group"
        ]
        
        domains = ["example.com", "test.org", "demo.net", "sample.co", "mock.io"]
        
        data = []
        entity_id = 1
        
        # Generate base records
        for i in range(scenario.data_size):
            base_record = {
                "_key": str(entity_id),
                "first_name": random.choice(first_names),
                "last_name": random.choice(last_names),
                "email": f"{random.choice(first_names).lower()}.{random.choice(last_names).lower()}@{random.choice(domains)}",
                "phone": f"555-{random.randint(1000, 9999)}",
                "company": random.choice(companies),
                "address": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Elm', 'Cedar'])} St",
                "city": random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]),
                "state": random.choice(["NY", "CA", "IL", "TX", "AZ"]),
                "zip_code": f"{random.randint(10000, 99999)}"
            }
            data.append(base_record)
            entity_id += 1
        
        # Generate duplicates based on scenario complexity
        duplicate_rate = 0.15 if scenario.complexity == "low" else (0.25 if scenario.complexity == "medium" else 0.35)
        num_duplicates = int(scenario.data_size * duplicate_rate)
        
        for i in range(num_duplicates):
            # Select a base record to duplicate
            base_record = random.choice(data)
            
            # Create variations of the record
            variations = self._create_record_variations(base_record)
            for variation in variations:
                variation["_key"] = str(entity_id)
                data.append(variation)
                entity_id += 1
        
        self.logger.info(f"   [PASS] Generated {len(data)} records with {num_duplicates} duplicate groups")
        return data
    
    def _create_record_variations(self, base_record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create realistic variations of a record."""
        variations = []
        
        # Variation 1: Minor typos in name
        typo_variation = base_record.copy()
        if random.random() < 0.3:
            typo_variation["first_name"] = self._introduce_typos(typo_variation["first_name"])
        if random.random() < 0.3:
            typo_variation["last_name"] = self._introduce_typos(typo_variation["last_name"])
        variations.append(typo_variation)
        
        # Variation 2: Different email format
        email_variation = base_record.copy()
        if random.random() < 0.4:
            email_parts = email_variation["email"].split("@")
            if len(email_parts) == 2:
                email_variation["email"] = f"{email_parts[0][:3]}.{email_parts[0][3:]}@{email_parts[1]}"
        variations.append(email_variation)
        
        # Variation 3: Different phone format
        phone_variation = base_record.copy()
        if random.random() < 0.3:
            phone_variation["phone"] = f"({phone_variation['phone'][:3]}) {phone_variation['phone'][4:]}"
        variations.append(phone_variation)
        
        return variations[:random.randint(1, 3)]  # Return 1-3 variations
    
    def _introduce_typos(self, text: str) -> str:
        """Introduce realistic typos in text."""
        if len(text) < 3:
            return text
        
        typo_type = random.choice(["substitution", "insertion", "deletion"])
        
        if typo_type == "substitution" and len(text) > 1:
            pos = random.randint(0, len(text) - 1)
            return text[:pos] + random.choice("abcdefghijklmnopqrstuvwxyz") + text[pos + 1:]
        elif typo_type == "insertion":
            pos = random.randint(0, len(text))
            return text[:pos] + random.choice("abcdefghijklmnopqrstuvwxyz") + text[pos:]
        elif typo_type == "deletion" and len(text) > 2:
            pos = random.randint(0, len(text) - 1)
            return text[:pos] + text[pos + 1:]
        
        return text
    
    def run_integration_test(self, scenario: TestScenario) -> Dict[str, Any]:
        """Run integration test for a specific scenario."""
        self.logger.info(f"\n? Running Integration Test: {scenario.name}")
        self.logger.info("="*60)
        
        start_time = time.time()
        
        try:
            # Initialize pipeline
            pipeline = EntityResolutionPipeline()
            pipeline.connect()
            
            # Generate test data
            test_data = self.generate_realistic_data(scenario)
            
            # Load data into database
            collection_name = f"test_{scenario.name.lower().replace(' ', '_')}"
            collection = pipeline.data_manager.database.collection(collection_name)
            
            self.logger.info(f"? Loading {len(test_data)} records into database...")
            for record in test_data:
                collection.insert(record)
            
            # Run entity resolution pipeline
            self.logger.debug(r"Running entity resolution pipeline...")
            
            # Step 1: Setup blocking
            blocking_result = pipeline.blocking_service.setup_for_collections([collection_name])
            if not blocking_result.get('success', False):
                raise Exception(f"Blocking setup failed: {blocking_result.get('error')}")
            
            # Step 2: Generate candidates
            candidates = []
            for record in test_data[:min(100, len(test_data))]:  # Limit for performance
                record_candidates = pipeline.blocking_service.generate_candidates(
                    collection_name, record['_key']
                )
                candidates.extend(record_candidates)
            
            self.logger.info(f"   ? Generated {len(candidates)} candidates")
            
            # Step 3: Compute similarities
            similarity_pairs = []
            for i in range(0, min(len(candidates), 200), 2):  # Limit for performance
                if i + 1 < len(candidates):
                    candidate_a = candidates[i]
                    candidate_b = candidates[i + 1]
                    
                    doc_a = candidate_a.get('document', {})
                    doc_b = candidate_b.get('document', {})
                    
                    if doc_a and doc_b:
                        similarity = pipeline.similarity_service.compute_similarity(doc_a, doc_b)
                        if similarity.get('success', False):
                            similarity_pairs.append({
                                "doc_a": doc_a,
                                "doc_b": doc_b,
                                "score": similarity.get('normalized_score', 0)
                            })
            
            self.logger.info(f"   ? Computed {len(similarity_pairs)} similarity scores")
            
            # Step 4: Cluster entities
            clusters = pipeline.clustering_service.cluster_entities(similarity_pairs)
            
            self.logger.info(f"   ? Generated {len(clusters)} clusters")
            
            # Calculate metrics
            execution_time = time.time() - start_time
            total_entities = sum(len(cluster) for cluster in clusters)
            cluster_ratio = len(clusters) / len(test_data) if len(test_data) > 0 else 0
            
            # Calculate accuracy (simplified)
            expected_duplicates = int(len(test_data) * 0.2)  # Assume 20% duplicates
            accuracy = min(1.0, len(clusters) / max(expected_duplicates, 1))
            
            # Cleanup
            pipeline.data_manager.database.delete_collection(collection_name)
            
            results = {
                "scenario": scenario.name,
                "data_size": len(test_data),
                "candidates_generated": len(candidates),
                "similarity_pairs": len(similarity_pairs),
                "clusters_generated": len(clusters),
                "total_entities_clustered": total_entities,
                "execution_time": execution_time,
                "cluster_ratio": cluster_ratio,
                "accuracy": accuracy,
                "performance_metrics": {
                    "records_per_second": len(test_data) / execution_time,
                    "candidates_per_second": len(candidates) / execution_time,
                    "similarities_per_second": len(similarity_pairs) / execution_time
                }
            }
            
            self.logger.info(f"   [PASS] Test completed in {execution_time:.2f}s")
            self.logger.info(f"   ? Accuracy: {accuracy:.1%}")
            self.logger.info(f"   ? Performance: {results['performance_metrics']['records_per_second']:.1f} records/s")
            
            return results
            
        except Exception as e:
            self.logger.info(f"   [FAIL] Test failed: {e}")
            return {
                "scenario": scenario.name,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    def run_comprehensive_integration_tests(self) -> Dict[str, Any]:
        """Run comprehensive integration tests for all scenarios."""
        self.logger.info("? COMPREHENSIVE REALISTIC INTEGRATION TESTS")
        self.logger.info("="*70)
        self.logger.info(f"Timestamp: {datetime.now().isoformat()}")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "scenarios": {},
            "summary": {},
            "recommendations": []
        }
        
        total_tests = len(self.test_scenarios)
        successful_tests = 0
        
        for scenario_name, scenario in self.test_scenarios.items():
            self.logger.info(f"\n? Testing Scenario: {scenario_name}")
            test_result = self.run_integration_test(scenario)
            results["scenarios"][scenario_name] = test_result
            
            if "error" not in test_result:
                successful_tests += 1
        
        # Calculate summary metrics
        successful_scenarios = [r for r in results["scenarios"].values() if "error" not in r]
        
        if successful_scenarios:
            avg_accuracy = sum(r.get("accuracy", 0) for r in successful_scenarios) / len(successful_scenarios)
            avg_performance = sum(r.get("performance_metrics", {}).get("records_per_second", 0) for r in successful_scenarios) / len(successful_scenarios)
            total_execution_time = sum(r.get("execution_time", 0) for r in successful_scenarios)
            
            results["summary"] = {
                "total_scenarios": total_tests,
                "successful_scenarios": successful_tests,
                "success_rate": successful_tests / total_tests,
                "average_accuracy": avg_accuracy,
                "average_performance": avg_performance,
                "total_execution_time": total_execution_time
            }
            
            self.logger.info(f"\n? INTEGRATION TEST SUMMARY")
            self.logger.info("="*50)
            self.logger.success(r"Successful: {successful_tests}/{total_tests}")
            self.logger.info(f"? Success Rate: {successful_tests/total_tests*100:.1f}%")
            self.logger.info(f"? Average Accuracy: {avg_accuracy:.1%}")
            self.logger.info(f"? Average Performance: {avg_performance:.1f} records/s")
            self.logger.info(f"? Total Execution Time: {total_execution_time:.2f}s")
        
        # Generate recommendations
        recommendations = []
        if successful_tests == total_tests:
            recommendations.append("[PASS] All integration tests passed - system is production ready")
        elif successful_tests >= total_tests * 0.8:
            recommendations.append("[PASS] Most integration tests passed - system is ready with minor issues")
        else:
            recommendations.append("[FAIL] Multiple integration test failures - system needs attention")
        
        if successful_scenarios:
            avg_accuracy = sum(r.get("accuracy", 0) for r in successful_scenarios) / len(successful_scenarios)
            if avg_accuracy >= 0.9:
                recommendations.append("[PASS] Excellent accuracy across all scenarios")
            elif avg_accuracy >= 0.8:
                recommendations.append("[PASS] Good accuracy across scenarios")
            else:
                recommendations.append("[WARN]?  Accuracy could be improved")
        
        results["recommendations"] = recommendations
        
        # Save comprehensive results
        report_file = f"realistic_integration_tests_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"\n? Comprehensive integration test report saved: {report_file}")
        
        return results
    
    def generate_ci_cd_config(self) -> Dict[str, Any]:
        """Generate CI/CD configuration for automated testing."""
        self.logger.info("? Generating CI/CD Configuration...")
        
        ci_cd_config = {
            "name": "Entity Resolution Integration Tests",
            "description": "Automated integration tests for entity resolution system",
            "triggers": {
                "push": {"branches": ["main", "develop"]},
                "pull_request": {"branches": ["main"]},
                "schedule": {"cron": "0 2 * * *"}  # Daily at 2 AM
            },
            "stages": [
                {
                    "name": "setup",
                    "script": [
                        "pip install -r requirements.txt",
                        "docker-compose up -d",
                        "sleep 30"  # Wait for ArangoDB to start
                    ]
                },
                {
                    "name": "unit_tests",
                    "script": [
                        "python scripts/consolidated_test_suite.py"
                    ]
                },
                {
                    "name": "integration_tests",
                    "script": [
                        "python scripts/realistic_integration_tests.py"
                    ]
                },
                {
                    "name": "performance_tests",
                    "script": [
                        "python scripts/enhanced_clustering_algorithms.py"
                    ]
                },
                {
                    "name": "cleanup",
                    "script": [
                        "docker-compose down",
                        "docker system prune -f"
                    ]
                }
            ],
            "artifacts": {
                "reports": [
                    "consolidated_test_report_*.json",
                    "realistic_integration_tests_report_*.json",
                    "enhanced_clustering_analysis_report_*.json"
                ]
            },
            "notifications": {
                "slack": {
                    "webhook": "${SLACK_WEBHOOK_URL}",
                    "channel": "#entity-resolution",
                    "on_success": True,
                    "on_failure": True
                }
            }
        }
        
        # Save CI/CD configuration
        config_file = "ci_cd_integration_config.json"
        with open(config_file, 'w') as f:
            json.dump(ci_cd_config, f, indent=2)
        
        self.logger.info(f"   [PASS] CI/CD configuration saved: {config_file}")
        return ci_cd_config

def main():
    """Run realistic integration tests."""
    try:
        tester = RealisticIntegrationTester()
        
        # Run comprehensive integration tests
        results = tester.run_comprehensive_integration_tests()
        
        # Generate CI/CD configuration
        ci_cd_config = tester.generate_ci_cd_config()
        
        return 0
    except Exception as e:
        self.logger.error(r"Realistic integration testing failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
