#!/usr/bin/env python3
"""
Focused Similarity Service Performance Test

Tests only the similarity service to demonstrate Foxx vs Python performance.
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from entity_resolution.utils.config import Config, get_config
from entity_resolution.utils.logging import get_logger
from entity_resolution.services.similarity_service import SimilarityService

logger = get_logger(__name__)

def test_similarity_performance():
    """Test similarity service performance in both modes"""
    config = get_config()
    
    # Test documents
    test_pairs = [
        ({"first_name": "John", "last_name": "Smith", "email": "john@example.com"},
         {"first_name": "Jon", "last_name": "Smith", "email": "john@example.com"}),
        ({"first_name": "Jane", "last_name": "Doe", "email": "jane@company.com"},
         {"first_name": "Jane", "last_name": "Doe", "email": "j.doe@company.com"}),
        ({"first_name": "Michael", "last_name": "Johnson", "email": "mike@test.com"},
         {"first_name": "Mike", "last_name": "Johnson", "email": "mike@test.com"}),
        ({"first_name": "Sarah", "last_name": "Williams", "email": "sarah@demo.org"},
         {"first_name": "Sara", "last_name": "Williams", "email": "sarah@demo.org"}),
        ({"first_name": "David", "last_name": "Brown", "email": "david@sample.net"},
         {"first_name": "Dave", "last_name": "Brown", "email": "d.brown@sample.net"})
    ]
    
    # Test Python mode (forced fallback)
    logger.info("Testing Python mode (fallback)...")
    similarity_service = SimilarityService(config)
    similarity_service.foxx_available = False  # Force Python mode
    
    start_time = time.time()
    python_results = []
    
    for doc_a, doc_b in test_pairs * 20:  # 100 comparisons
        try:
            result = similarity_service.compute_similarity(doc_a, doc_b)
            python_results.append(result)
        except Exception as e:
            logger.warning(f"Python similarity failed: {e}")
    
    python_time = time.time() - start_time
    python_throughput = len(python_results) / python_time if python_time > 0 else 0
    
    logger.info(f"Python Results: {len(python_results)} processed in {python_time:.3f}s")
    logger.info(f"Python Throughput: {python_throughput:.2f} computations/second")
    
    # Test Foxx mode
    logger.info("Testing Foxx mode...")
    similarity_service = SimilarityService(config)
    similarity_service.connect()  # Check for Foxx availability
    
    if similarity_service.foxx_available:
        start_time = time.time()
        foxx_results = []
        
        for doc_a, doc_b in test_pairs * 20:  # 100 comparisons
            try:
                result = similarity_service.compute_similarity(doc_a, doc_b)
                foxx_results.append(result)
            except Exception as e:
                logger.warning(f"Foxx similarity failed: {e}")
        
        foxx_time = time.time() - start_time
        foxx_throughput = len(foxx_results) / foxx_time if foxx_time > 0 else 0
        
        logger.info(f"Foxx Results: {len(foxx_results)} processed in {foxx_time:.3f}s")
        logger.info(f"Foxx Throughput: {foxx_throughput:.2f} computations/second")
        
        # Calculate improvement
        if python_throughput > 0 and foxx_throughput > 0:
            improvement = foxx_throughput / python_throughput
            logger.info(f"Performance Improvement: {improvement:.2f}x faster")
            
            return {
                "python_throughput": python_throughput,
                "foxx_throughput": foxx_throughput,
                "improvement_factor": improvement,
                "python_time": python_time,
                "foxx_time": foxx_time
            }
    else:
        logger.warning("Foxx service not available for comparison")
        return {
            "python_throughput": python_throughput,
            "foxx_available": False
        }

def main():
    """Main test function"""
    logger.info("Similarity Service Performance Test")
    logger.info("=" * 40)
    
    results = test_similarity_performance()
    
    logger.info("")
    logger.info("PERFORMANCE TEST SUMMARY")
    logger.info("=" * 30)
    
    if results.get("foxx_available", True):
        logger.info(f"Python Mode: {results['python_throughput']:.2f} ops/sec")
        logger.info(f"Foxx Mode: {results['foxx_throughput']:.2f} ops/sec")
        logger.info(f"Improvement: {results['improvement_factor']:.2f}x faster")
        logger.info(f"Time saved: {((results['python_time'] - results['foxx_time']) / results['python_time'] * 100):.1f}%")
    else:
        logger.info(f"Python Mode: {results['python_throughput']:.2f} ops/sec")
        logger.info("Foxx Mode: Not available")
    
    return results

if __name__ == "__main__":
    main()
