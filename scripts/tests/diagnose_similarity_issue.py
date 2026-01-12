#!/usr/bin/env python3
"""
Diagnose Similarity Computation Issue

This script diagnoses why similarity scores are returning 0.000
by testing the similarity service with known data and detailed logging.
"""

import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

class SimilarityDiagnostic:
    """Diagnostic tool for similarity computation issues."""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.similarity_service = SimilarityService()
        
    def test_basic_similarity(self):
        """Test basic similarity computation with known data."""
        print("? Testing Basic Similarity Computation")
        print("="*50)
        
        # Test data with known similarities
        test_cases = [
            {
                "name": "Identical Records",
                "doc_a": {
                    "first_name": "John",
                    "last_name": "Smith", 
                    "email": "john.smith@example.com",
                    "phone": "555-1234"
                },
                "doc_b": {
                    "first_name": "John",
                    "last_name": "Smith",
                    "email": "john.smith@example.com", 
                    "phone": "555-1234"
                },
                "expected_score": "High (close to 1.0)"
            },
            {
                "name": "Similar Records",
                "doc_a": {
                    "first_name": "John",
                    "last_name": "Smith",
                    "email": "john.smith@example.com",
                    "phone": "555-1234"
                },
                "doc_b": {
                    "first_name": "Jon",
                    "last_name": "Smith",
                    "email": "j.smith@example.com",
                    "phone": "555-1234"
                },
                "expected_score": "Medium (0.5-0.8)"
            },
            {
                "name": "Different Records",
                "doc_a": {
                    "first_name": "John",
                    "last_name": "Smith",
                    "email": "john.smith@example.com",
                    "phone": "555-1234"
                },
                "doc_b": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane.doe@example.com",
                    "phone": "555-5678"
                },
                "expected_score": "Low (close to 0.0)"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n? Test Case {i}: {test_case['name']}")
            print(f"   Expected: {test_case['expected_score']}")
            
            try:
                # Compute similarity with detailed output
                result = self.similarity_service.compute_similarity(
                    test_case['doc_a'], 
                    test_case['doc_b'],
                    include_details=True
                )
                
                print(f"   Result: {json.dumps(result, indent=2)}")
                
                if result.get('success'):
                    score = result.get('total_score', 0)
                    normalized = result.get('normalized_score', 0)
                    print(f"   [PASS] Total Score: {score:.6f}")
                    print(f"   [PASS] Normalized Score: {normalized:.6f}")
                    print(f"   [PASS] Decision: {result.get('decision', 'unknown')}")
                    
                    if 'field_scores' in result:
                        print(f"   ? Field Scores:")
                        for field, scores in result['field_scores'].items():
                            print(f"      {field}: {scores['similarity']:.3f} (weight: {scores['weight']:.3f})")
                else:
                    print(f"   [FAIL] Error: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"   [FAIL] Exception: {e}")
    
    def test_field_weights(self):
        """Test field weights configuration."""
        print("\n? Testing Field Weights Configuration")
        print("="*50)
        
        try:
            # Get field weights
            field_weights = self.similarity_service.get_field_weights()
            print(f"? Field Weights Configuration:")
            print(json.dumps(field_weights, indent=2))
            
            # Test with a simple case
            doc_a = {"first_name": "John", "last_name": "Smith"}
            doc_b = {"first_name": "John", "last_name": "Smith"}
            
            print(f"\n? Testing with simple case:")
            print(f"   Doc A: {doc_a}")
            print(f"   Doc B: {doc_b}")
            
            result = self.similarity_service.compute_similarity(doc_a, doc_b, include_details=True)
            print(f"   Result: {json.dumps(result, indent=2)}")
            
        except Exception as e:
            print(f"[FAIL] Field weights test failed: {e}")
    
    def test_individual_algorithms(self):
        """Test individual similarity algorithms."""
        print("\n? Testing Individual Similarity Algorithms")
        print("="*50)
        
        test_strings = [
            ("John", "John"),
            ("John", "Jon"),
            ("John", "Jane"),
            ("Smith", "Smith"),
            ("Smith", "Smyth"),
            ("Smith", "Doe")
        ]
        
        for str_a, str_b in test_strings:
            print(f"\n? Testing: '{str_a}' vs '{str_b}'")
            
            try:
                # Test n-gram similarity
                ngram_sim = self.similarity_service._ngram_similarity(str_a, str_b)
                print(f"   N-gram: {ngram_sim:.3f}")
                
                # Test Levenshtein similarity
                lev_sim = self.similarity_service._normalized_levenshtein(str_a, str_b)
                print(f"   Levenshtein: {lev_sim:.3f}")
                
                # Test Jaro-Winkler similarity
                jw_sim = self.similarity_service._jaro_winkler_similarity(str_a, str_b)
                print(f"   Jaro-Winkler: {jw_sim:.3f}")
                
                # Test phonetic similarity
                ph_sim = self.similarity_service._phonetic_similarity(str_a, str_b)
                print(f"   Phonetic: {ph_sim:.3f}")
                
            except Exception as e:
                print(f"   [FAIL] Algorithm test failed: {e}")
    
    def test_fellegi_sunter_framework(self):
        """Test the Fellegi-Sunter framework directly."""
        print("\n? Testing Fellegi-Sunter Framework")
        print("="*50)
        
        # Test with known similarities
        test_similarities = {
            "first_name_ngram": 0.9,
            "last_name_ngram": 0.95,
            "email_exact": 1.0,
            "phone_exact": 1.0
        }
        
        field_weights = self.similarity_service.get_field_weights()
        
        print(f"? Test Similarities: {test_similarities}")
        print(f"? Field Weights: {json.dumps(field_weights, indent=2)}")
        
        try:
            result = self.similarity_service._compute_fellegi_sunter_score(
                test_similarities, field_weights, include_details=True
            )
            print(f"? Fellegi-Sunter Result: {json.dumps(result, indent=2)}")
            
        except Exception as e:
            print(f"[FAIL] Fellegi-Sunter test failed: {e}")
    
    def run_full_diagnosis(self):
        """Run complete similarity diagnosis."""
        print("? SIMILARITY COMPUTATION DIAGNOSIS")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        try:
            self.test_basic_similarity()
            self.test_field_weights()
            self.test_individual_algorithms()
            self.test_fellegi_sunter_framework()
            
            print(f"\n[PASS] Diagnosis completed successfully!")
            
        except Exception as e:
            print(f"[FAIL] Diagnosis failed: {e}")
            return False
        
        return True

def main():
    """Run similarity diagnosis."""
    try:
        diagnostic = SimilarityDiagnostic()
        success = diagnostic.run_full_diagnosis()
        return 0 if success else 1
    except Exception as e:
        print(f"[FAIL] Diagnostic failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
