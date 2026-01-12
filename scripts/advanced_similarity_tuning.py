#!/usr/bin/env python3
"""
Advanced Similarity Algorithm Tuning

This script provides advanced similarity algorithm tuning capabilities for different
business scenarios and use cases.
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

@dataclass
class BusinessScenario:
    """Business scenario configuration for similarity tuning."""
    name: str
    description: str
    field_weights: Dict[str, Any]
    global_thresholds: Dict[str, float]
    expected_behavior: str

class AdvancedSimilarityTuner:
    """Advanced similarity algorithm tuning for different business scenarios."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.similarity_service = SimilarityService()
        
        # Business scenarios for tuning
        self.business_scenarios = {
            "high_precision": BusinessScenario(
                name="High Precision (Financial Services)",
                description="Minimize false positives, prioritize accuracy over recall",
                field_weights={
                    "email_exact": {"m_prob": 0.98, "u_prob": 0.001, "threshold": 1.0, "importance": 2.0},
                    "phone_exact": {"m_prob": 0.95, "u_prob": 0.002, "threshold": 1.0, "importance": 1.8},
                    "last_name_ngram": {"m_prob": 0.95, "u_prob": 0.01, "threshold": 0.8, "importance": 1.5},
                    "first_name_ngram": {"m_prob": 0.90, "u_prob": 0.02, "threshold": 0.8, "importance": 1.2},
                    "company_ngram": {"m_prob": 0.85, "u_prob": 0.03, "threshold": 0.7, "importance": 1.0}
                },
                global_thresholds={"upper_threshold": 4.0, "lower_threshold": -0.5},
                expected_behavior="Very strict matching, low false positive rate"
            ),
            
            "high_recall": BusinessScenario(
                name="High Recall (Marketing Analytics)",
                description="Maximize true positives, prioritize finding all potential matches",
                field_weights={
                    "email_exact": {"m_prob": 0.90, "u_prob": 0.01, "threshold": 1.0, "importance": 1.5},
                    "phone_exact": {"m_prob": 0.85, "u_prob": 0.02, "threshold": 1.0, "importance": 1.3},
                    "last_name_ngram": {"m_prob": 0.80, "u_prob": 0.05, "threshold": 0.6, "importance": 1.2},
                    "first_name_ngram": {"m_prob": 0.75, "u_prob": 0.08, "threshold": 0.6, "importance": 1.0},
                    "company_ngram": {"m_prob": 0.70, "u_prob": 0.10, "threshold": 0.5, "importance": 0.8}
                },
                global_thresholds={"upper_threshold": 2.0, "lower_threshold": -1.0},
                expected_behavior="Liberal matching, high recall rate"
            ),
            
            "balanced": BusinessScenario(
                name="Balanced (General Business)",
                description="Balance between precision and recall for general use",
                field_weights={
                    "email_exact": {"m_prob": 0.95, "u_prob": 0.001, "threshold": 1.0, "importance": 1.8},
                    "phone_exact": {"m_prob": 0.90, "u_prob": 0.005, "threshold": 1.0, "importance": 1.5},
                    "last_name_ngram": {"m_prob": 0.90, "u_prob": 0.015, "threshold": 0.7, "importance": 1.3},
                    "first_name_ngram": {"m_prob": 0.85, "u_prob": 0.02, "threshold": 0.7, "importance": 1.0},
                    "company_ngram": {"m_prob": 0.80, "u_prob": 0.02, "threshold": 0.7, "importance": 0.9}
                },
                global_thresholds={"upper_threshold": 3.0, "lower_threshold": -0.8},
                expected_behavior="Balanced precision and recall"
            ),
            
            "ecommerce": BusinessScenario(
                name="E-commerce (Customer Matching)",
                description="Optimized for e-commerce customer deduplication",
                field_weights={
                    "email_exact": {"m_prob": 0.95, "u_prob": 0.001, "threshold": 1.0, "importance": 2.0},
                    "phone_exact": {"m_prob": 0.85, "u_prob": 0.01, "threshold": 1.0, "importance": 1.5},
                    "last_name_ngram": {"m_prob": 0.85, "u_prob": 0.02, "threshold": 0.7, "importance": 1.2},
                    "first_name_ngram": {"m_prob": 0.80, "u_prob": 0.03, "threshold": 0.6, "importance": 1.0},
                    "address_ngram": {"m_prob": 0.75, "u_prob": 0.05, "threshold": 0.6, "importance": 0.8}
                },
                global_thresholds={"upper_threshold": 2.5, "lower_threshold": -0.5},
                expected_behavior="E-commerce optimized matching"
            ),
            
            "healthcare": BusinessScenario(
                name="Healthcare (Patient Matching)",
                description="Strict matching for healthcare patient records",
                field_weights={
                    "email_exact": {"m_prob": 0.98, "u_prob": 0.001, "threshold": 1.0, "importance": 2.5},
                    "phone_exact": {"m_prob": 0.95, "u_prob": 0.002, "threshold": 1.0, "importance": 2.0},
                    "last_name_ngram": {"m_prob": 0.95, "u_prob": 0.005, "threshold": 0.8, "importance": 2.0},
                    "first_name_ngram": {"m_prob": 0.90, "u_prob": 0.01, "threshold": 0.8, "importance": 1.8},
                    "date_of_birth": {"m_prob": 0.98, "u_prob": 0.001, "threshold": 1.0, "importance": 2.2}
                },
                global_thresholds={"upper_threshold": 4.5, "lower_threshold": -0.2},
                expected_behavior="Very strict healthcare matching"
            )
        }
    
    def test_scenario_performance(self, scenario_name: str, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test performance of a specific business scenario."""
        print(f"? Testing {scenario_name} Scenario")
        print("="*50)
        
        scenario = self.business_scenarios[scenario_name]
        
        # Configure similarity service with scenario weights
        self.similarity_service.configure_field_weights(scenario.field_weights)
        
        results = {
            "scenario": scenario_name,
            "description": scenario.description,
            "test_cases": [],
            "performance_metrics": {},
            "recommendations": []
        }
        
        # Test with provided data
        for i, test_case in enumerate(test_data):
            try:
                result = self.similarity_service.compute_similarity(
                    test_case['doc_a'], 
                    test_case['doc_b'],
                    include_details=True
                )
                
                if result.get('success', False):
                    score = result.get('normalized_score', 0)
                    decision = result.get('decision', 'unknown')
                    
                    test_result = {
                        "test_case": i + 1,
                        "expected": test_case.get('expected_decision', 'unknown'),
                        "actual": decision,
                        "score": score,
                        "correct": decision == test_case.get('expected_decision', 'unknown')
                    }
                    
                    results["test_cases"].append(test_result)
                    print(f"   Test {i+1}: {decision} (score: {score:.3f}) - {'[PASS]' if test_result['correct'] else '[FAIL]'}")
                else:
                    print(f"   Test {i+1}: [FAIL] Failed - {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"   Test {i+1}: [FAIL] Exception - {e}")
        
        # Calculate performance metrics
        correct_predictions = sum(1 for tc in results["test_cases"] if tc.get('correct', False))
        total_tests = len(results["test_cases"])
        accuracy = correct_predictions / total_tests if total_tests > 0 else 0
        
        results["performance_metrics"] = {
            "accuracy": accuracy,
            "correct_predictions": correct_predictions,
            "total_tests": total_tests,
            "scenario_behavior": scenario.expected_behavior
        }
        
        print(f"   ? Accuracy: {accuracy:.1%} ({correct_predictions}/{total_tests})")
        print(f"   ? Behavior: {scenario.expected_behavior}")
        
        return results
    
    def compare_scenarios(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare performance across all business scenarios."""
        print("? Comparing All Business Scenarios")
        print("="*60)
        
        comparison_results = {
            "timestamp": datetime.now().isoformat(),
            "scenarios": {},
            "best_scenario": None,
            "recommendations": []
        }
        
        scenario_performances = {}
        
        for scenario_name in self.business_scenarios.keys():
            print(f"\n? Testing {scenario_name}...")
            results = self.test_scenario_performance(scenario_name, test_data)
            comparison_results["scenarios"][scenario_name] = results
            scenario_performances[scenario_name] = results["performance_metrics"]["accuracy"]
        
        # Find best performing scenario
        best_scenario = max(scenario_performances.items(), key=lambda x: x[1])
        comparison_results["best_scenario"] = {
            "name": best_scenario[0],
            "accuracy": best_scenario[1],
            "description": self.business_scenarios[best_scenario[0]].description
        }
        
        print(f"\n? Best Performing Scenario: {best_scenario[0]} ({best_scenario[1]:.1%} accuracy)")
        
        # Generate recommendations
        recommendations = []
        for scenario_name, accuracy in scenario_performances.items():
            if accuracy >= 0.9:
                recommendations.append(f"[PASS] {scenario_name}: Excellent performance ({accuracy:.1%})")
            elif accuracy >= 0.8:
                recommendations.append(f"[PASS] {scenario_name}: Good performance ({accuracy:.1%})")
            elif accuracy >= 0.7:
                recommendations.append(f"[WARN]?  {scenario_name}: Acceptable performance ({accuracy:.1%})")
            else:
                recommendations.append(f"[FAIL] {scenario_name}: Needs improvement ({accuracy:.1%})")
        
        comparison_results["recommendations"] = recommendations
        
        return comparison_results
    
    def generate_optimized_config(self, scenario_name: str, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate optimized configuration based on test results."""
        print(f"? Generating Optimized Configuration for {scenario_name}")
        print("="*60)
        
        scenario = self.business_scenarios[scenario_name]
        
        # Analyze test results to optimize parameters
        correct_cases = [tc for tc in test_results["test_cases"] if tc.get('correct', False)]
        incorrect_cases = [tc for tc in test_results["test_cases"] if not tc.get('correct', False)]
        
        # Calculate score distributions
        correct_scores = [tc['score'] for tc in correct_cases]
        incorrect_scores = [tc['score'] for tc in incorrect_cases]
        
        if correct_scores and incorrect_scores:
            avg_correct_score = sum(correct_scores) / len(correct_scores)
            avg_incorrect_score = sum(incorrect_scores) / len(incorrect_scores)
            
            # Optimize thresholds based on score distributions
            optimal_upper_threshold = (avg_correct_score + avg_incorrect_score) / 2
            optimal_lower_threshold = avg_incorrect_score - 0.5
            
            optimized_config = {
                "scenario": scenario_name,
                "optimized_weights": scenario.field_weights.copy(),
                "optimized_thresholds": {
                    "upper_threshold": max(optimal_upper_threshold, 2.0),
                    "lower_threshold": min(optimal_lower_threshold, -1.0)
                },
                "performance_analysis": {
                    "avg_correct_score": avg_correct_score,
                    "avg_incorrect_score": avg_incorrect_score,
                    "score_separation": avg_correct_score - avg_incorrect_score
                },
                "recommendations": []
            }
            
            # Generate specific recommendations
            if avg_correct_score - avg_incorrect_score < 1.0:
                optimized_config["recommendations"].append(
                    "Consider increasing field importance weights for better separation"
                )
            
            if len(incorrect_cases) > len(correct_cases) * 0.2:
                optimized_config["recommendations"].append(
                    "High error rate - consider adjusting m_prob and u_prob values"
                )
            
            print(f"   ? Average correct score: {avg_correct_score:.3f}")
            print(f"   ? Average incorrect score: {avg_incorrect_score:.3f}")
            print(f"   ? Score separation: {avg_correct_score - avg_incorrect_score:.3f}")
            print(f"   ? Optimal upper threshold: {optimized_config['optimized_thresholds']['upper_threshold']:.3f}")
            print(f"   ? Optimal lower threshold: {optimized_config['optimized_thresholds']['lower_threshold']:.3f}")
            
            return optimized_config
        else:
            print("   [WARN]?  Insufficient data for optimization")
            return {"scenario": scenario_name, "status": "insufficient_data"}
    
    def run_comprehensive_tuning(self) -> Dict[str, Any]:
        """Run comprehensive similarity algorithm tuning."""
        print("? ADVANCED SIMILARITY ALGORITHM TUNING")
        print("="*70)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Test data for different scenarios
        test_data = [
            {
                "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john.smith@example.com", "phone": "555-1234"},
                "doc_b": {"first_name": "John", "last_name": "Smith", "email": "john.smith@example.com", "phone": "555-1234"},
                "expected_decision": "match"
            },
            {
                "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john.smith@example.com", "phone": "555-1234"},
                "doc_b": {"first_name": "Jon", "last_name": "Smith", "email": "j.smith@example.com", "phone": "555-1234"},
                "expected_decision": "match"
            },
            {
                "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john.smith@example.com", "phone": "555-1234"},
                "doc_b": {"first_name": "Jane", "last_name": "Doe", "email": "jane.doe@example.com", "phone": "555-5678"},
                "expected_decision": "non_match"
            },
            {
                "doc_a": {"first_name": "John", "last_name": "Smith", "email": "john.smith@example.com", "phone": "555-1234"},
                "doc_b": {"first_name": "John", "last_name": "Smith", "email": "different@example.com", "phone": "555-9999"},
                "expected_decision": "possible_match"
            }
        ]
        
        # Compare all scenarios
        comparison_results = self.compare_scenarios(test_data)
        
        # Generate optimized configurations for each scenario
        optimized_configs = {}
        for scenario_name in self.business_scenarios.keys():
            scenario_results = comparison_results["scenarios"][scenario_name]
            optimized_config = self.generate_optimized_config(scenario_name, scenario_results)
            optimized_configs[scenario_name] = optimized_config
        
        # Save comprehensive results
        report_file = f"advanced_similarity_tuning_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "comparison_results": comparison_results,
                "optimized_configs": optimized_configs,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\n? Comprehensive tuning report saved: {report_file}")
        
        return {
            "comparison_results": comparison_results,
            "optimized_configs": optimized_configs
        }

def main():
    """Run advanced similarity algorithm tuning."""
    try:
        tuner = AdvancedSimilarityTuner()
        results = tuner.run_comprehensive_tuning()
        return 0
    except Exception as e:
        print(f"[FAIL] Advanced similarity tuning failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
