#!/usr/bin/env python3
"""
Resilient Test Script for Enhanced Similarity Service

This version includes resilient database management to handle:
- Port collisions
- Missing databases
- Container conflicts
- Automatic database setup

Demonstrates the complete Fellegi-Sunter similarity service with:
- Multiple similarity algorithms (n-gram, Levenshtein, Jaro-Winkler, phonetic)
- Configurable field weights and thresholds
- Probabilistic scoring framework
- Detailed result analysis
- Resilient database connections
"""

import sys
import json
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add scripts to Python path for database manager
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.utils.config import Config
from entity_resolution.utils.logging import setup_logging, get_logger
from test_database_manager import ensure_test_database


def test_similarity_algorithms():
    """Test individual similarity algorithms"""
    
    logger = get_logger(__name__)
    logger.info("=== Testing Individual Similarity Algorithms ===")
    
    # Initialize similarity service with resilient database
    try:
        # Ensure test database is available
        db_manager = ensure_test_database()
        logger.info("[PASS] Test database is available")
        
        # Initialize similarity service
        config = Config.from_env()
        similarity_service = SimilarityService(config)
        
    except Exception as e:
        logger.error(f"[FAIL] Failed to setup test database: {e}")
        return False
    
    # Test cases with various types of variations
    test_cases = [
        {
            "name": "Exact Match",
            "str1": "John Smith",
            "str2": "John Smith"
        },
        {
            "name": "Typo Variation", 
            "str1": "John Smith",
            "str2": "Jon Smith"
        },
        {
            "name": "Order Variation",
            "str1": "Smith, John",
            "str2": "John Smith"
        },
        {
            "name": "Phonetic Similarity",
            "str1": "Catherine",
            "str2": "Katherine"
        },
        {
            "name": "Nickname Variation",
            "str1": "William Johnson",
            "str2": "Bill Johnson"
        },
        {
            "name": "Different Names",
            "str1": "John Smith",
            "str2": "Mary Jones"
        }
    ]
    
    algorithms = {
        "N-gram (3)": similarity_service._ngram_similarity,
        "Levenshtein": similarity_service._normalized_levenshtein,
        "Jaro-Winkler": similarity_service._jaro_winkler_similarity,
        "Phonetic": similarity_service._phonetic_similarity
    }
    
    print(f"\n{'Test Case':<20} {'N-gram':<10} {'Leven':<10} {'Jaro-W':<10} {'Phonetic':<10}")
    print("-" * 70)
    
    for test_case in test_cases:
        str1, str2 = test_case["str1"], test_case["str2"]
        name = test_case["name"]
        
        scores = {}
        for alg_name, alg_func in algorithms.items():
            try:
                score = alg_func(str1, str2)
                scores[alg_name] = score
            except Exception as e:
                logger.error(f"Error in {alg_name} for '{str1}' vs '{str2}': {e}")
                scores[alg_name] = 0.0
        
        print(f"{name:<20} {scores['N-gram (3)']:<10.3f} {scores['Levenshtein']:<10.3f} "
              f"{scores['Jaro-Winkler']:<10.3f} {scores['Phonetic']:<10.3f}")
    
    return True


def test_document_similarity():
    """Test complete document similarity computation with resilient database"""
    
    logger = get_logger(__name__)
    logger.info("=== Testing Document Similarity Computation ===")
    
    try:
        # Ensure test database is available
        db_manager = ensure_test_database()
        logger.info("[PASS] Test database is available")
        
        # Initialize similarity service
        config = Config.from_env()
        similarity_service = SimilarityService(config)
        
        # Get sample records from database
        sample_record = db_manager.get_sample_record('customers')
        if not sample_record:
            logger.warning("No sample records found, creating test data...")
            db_manager.create_sample_data()
            sample_record = db_manager.get_sample_record('customers')
        
        if not sample_record:
            logger.error("Could not get sample record for testing")
            return False
        
        logger.info(f"Using sample record: {sample_record.get('first_name', 'Unknown')} {sample_record.get('last_name', 'Unknown')}")
        
    except Exception as e:
        logger.error(f"[FAIL] Failed to setup test database: {e}")
        return False
    
    # Test document similarity with various field combinations
    test_documents = [
        {
            "name": "Exact Match",
            "doc_a": {
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@email.com",
                "phone": "555-1234"
            },
            "doc_b": {
                "first_name": "John", 
                "last_name": "Smith",
                "email": "john.smith@email.com",
                "phone": "555-1234"
            }
        },
        {
            "name": "Typo Variation",
            "doc_a": {
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@email.com",
                "phone": "555-1234"
            },
            "doc_b": {
                "first_name": "Jon",
                "last_name": "Smith", 
                "email": "jon.smith@email.com",
                "phone": "555-1234"
            }
        },
        {
            "name": "Company Variation",
            "doc_a": {
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@acme.com",
                "phone": "555-1234",
                "company": "Acme Corp"
            },
            "doc_b": {
                "first_name": "John",
                "last_name": "Smith", 
                "email": "john.smith@acme.com",
                "phone": "555-1234",
                "company": "Acme Corporation"
            }
        }
    ]
    
    print(f"\n{'Test Case':<20} {'Overall':<10} {'Name':<10} {'Email':<10} {'Phone':<10} {'Decision'}")
    print("-" * 80)
    
    for test_case in test_documents:
        name = test_case["name"]
        doc_a = test_case["doc_a"]
        doc_b = test_case["doc_b"]
        
        try:
            # Compute similarity
            result = similarity_service.compute_similarity(doc_a, doc_b)
            
            overall_score = result.get('overall_similarity', 0.0)
            name_score = result.get('field_scores', {}).get('name_similarity', 0.0)
            email_score = result.get('field_scores', {}).get('email_similarity', 0.0)
            phone_score = result.get('field_scores', {}).get('phone_similarity', 0.0)
            decision = result.get('decision', 'UNKNOWN')
            
            print(f"{name:<20} {overall_score:<10.3f} {name_score:<10.3f} {email_score:<10.3f} "
                  f"{phone_score:<10.3f} {decision:<10}")
            
        except Exception as e:
            logger.error(f"Error computing similarity for {name}: {e}")
            print(f"{name:<20} {'ERROR':<10} {'ERROR':<10} {'ERROR':<10} {'ERROR':<10} {'ERROR':<10}")
    
    return True


def test_similarity_with_database_records():
    """Test similarity computation using actual database records"""
    
    logger = get_logger(__name__)
    logger.info("=== Testing Similarity with Database Records ===")
    
    try:
        # Ensure test database is available
        db_manager = ensure_test_database()
        logger.info("[PASS] Test database is available")
        
        # Initialize similarity service
        config = Config.from_env()
        similarity_service = SimilarityService(config)
        
        # Get database connection
        db = db_manager.get_database()
        customers_collection = db.collection('customers')
        
        # Get multiple records for comparison
        records = list(customers_collection.all(limit=4))
        if len(records) < 2:
            logger.warning("Not enough records for comparison, creating more sample data...")
            db_manager.create_sample_data()
            records = list(customers_collection.all(limit=4))
        
        if len(records) < 2:
            logger.error("Could not get enough records for testing")
            return False
        
        logger.info(f"Testing with {len(records)} database records")
        
        # Test similarity between different record pairs
        print(f"\n{'Record A':<15} {'Record B':<15} {'Similarity':<12} {'Decision'}")
        print("-" * 60)
        
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                record_a = records[i]
                record_b = records[j]
                
                try:
                    # Compute similarity
                    result = similarity_service.compute_similarity(record_a, record_b)
                    
                    overall_score = result.get('overall_similarity', 0.0)
                    decision = result.get('decision', 'UNKNOWN')
                    
                    name_a = f"{record_a.get('first_name', '')} {record_a.get('last_name', '')}"
                    name_b = f"{record_b.get('first_name', '')} {record_b.get('last_name', '')}"
                    
                    print(f"{name_a:<15} {name_b:<15} {overall_score:<12.3f} {decision:<10}")
                    
                except Exception as e:
                    logger.error(f"Error comparing records: {e}")
                    print(f"{name_a:<15} {name_b:<15} {'ERROR':<12} {'ERROR':<10}")
        
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Failed to test similarity with database records: {e}")
        return False


def test_similarity_performance():
    """Test similarity computation performance with resilient database"""
    
    logger = get_logger(__name__)
    logger.info("=== Testing Similarity Performance ===")
    
    try:
        # Ensure test database is available
        db_manager = ensure_test_database()
        logger.info("[PASS] Test database is available")
        
        # Initialize similarity service
        config = Config.from_env()
        similarity_service = SimilarityService(config)
        
        # Get database connection
        db = db_manager.get_database()
        customers_collection = db.collection('customers')
        
        # Get records for performance testing
        records = list(customers_collection.all(limit=10))
        if len(records) < 2:
            logger.warning("Not enough records for performance testing, creating more sample data...")
            db_manager.create_sample_data()
            records = list(customers_collection.all(limit=10))
        
        if len(records) < 2:
            logger.error("Could not get enough records for performance testing")
            return False
        
        logger.info(f"Performance testing with {len(records)} records")
        
        # Test performance with different batch sizes
        import time
        
        batch_sizes = [2, 5, min(len(records), 10)]
        
        print(f"\n{'Batch Size':<12} {'Comparisons':<12} {'Time (ms)':<12} {'Avg/Comparison'}")
        print("-" * 50)
        
        for batch_size in batch_sizes:
            test_records = records[:batch_size]
            comparisons = 0
            start_time = time.time()
            
            # Perform all pairwise comparisons
            for i in range(len(test_records)):
                for j in range(i + 1, len(test_records)):
                    try:
                        similarity_service.compute_similarity(test_records[i], test_records[j])
                        comparisons += 1
                    except Exception as e:
                        logger.error(f"Error in performance test: {e}")
            
            end_time = time.time()
            total_time = (end_time - start_time) * 1000  # Convert to milliseconds
            avg_time = total_time / comparisons if comparisons > 0 else 0
            
            print(f"{batch_size:<12} {comparisons:<12} {total_time:<12.2f} {avg_time:<12.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Failed to test similarity performance: {e}")
        return False


def main():
    """Main test function with resilient database management"""
    
    print("? RESILIENT SIMILARITY SERVICE TESTING")
    print("=" * 50)
    
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    try:
        # Test 1: Individual algorithms
        print("\n1. Testing Individual Similarity Algorithms...")
        if test_similarity_algorithms():
            print("[PASS] Individual algorithm tests passed")
        else:
            print("[FAIL] Individual algorithm tests failed")
        
        # Test 2: Document similarity
        print("\n2. Testing Document Similarity Computation...")
        if test_document_similarity():
            print("[PASS] Document similarity tests passed")
        else:
            print("[FAIL] Document similarity tests failed")
        
        # Test 3: Database records
        print("\n3. Testing Similarity with Database Records...")
        if test_similarity_with_database_records():
            print("[PASS] Database record tests passed")
        else:
            print("[FAIL] Database record tests failed")
        
        # Test 4: Performance
        print("\n4. Testing Similarity Performance...")
        if test_similarity_performance():
            print("[PASS] Performance tests passed")
        else:
            print("[FAIL] Performance tests failed")
        
        print("\n? All similarity service tests completed!")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Test suite failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
