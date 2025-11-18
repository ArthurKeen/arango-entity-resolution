#!/usr/bin/env python3
"""
Simple Round-Trip Test Script

Tests v3.0 components with real ArangoDB without pytest.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variables
os.environ['ARANGO_ROOT_PASSWORD'] = 'testpassword123'
os.environ['USE_DEFAULT_PASSWORD'] = 'true'
os.environ['ARANGO_HOST'] = 'localhost'
os.environ['ARANGO_PORT'] = '8529'
os.environ['ARANGO_DATABASE'] = 'entity_resolution_test'

from entity_resolution import (
    WeightedFieldSimilarity,
    BatchSimilarityService,
    get_database
)

def test_weighted_field_similarity():
    """Test WeightedFieldSimilarity."""
    print("\n" + "="*80)
    print("TEST 1: WeightedFieldSimilarity")
    print("="*80)
    
    doc1 = {
        "name": "Acme Corporation",
        "address": "123 Main Street",
        "city": "Boston",
        "state": "MA"
    }
    doc2 = {
        "name": "Acme Corp",
        "address": "123 Main St",
        "city": "Boston",
        "state": "MA"
    }
    
    similarity = WeightedFieldSimilarity(
        field_weights={
            "name": 0.4,
            "address": 0.3,
            "city": 0.2,
            "state": 0.1
        },
        algorithm="jaro_winkler"
    )
    
    score = similarity.compute(doc1, doc2)
    detailed = similarity.compute_detailed(doc1, doc2)
    
    print(f"✓ Similarity Score: {score:.4f}")
    print(f"✓ Field Scores: {detailed['field_scores']}")
    assert 0.7 <= score <= 1.0, f"Expected high similarity, got {score}"
    print("✓ PASSED")


def test_batch_similarity_service():
    """Test BatchSimilarityService with real database."""
    print("\n" + "="*80)
    print("TEST 2: BatchSimilarityService (with real database)")
    print("="*80)
    
    try:
        db = get_database()
        print("✓ Connected to database")
        
        # Create test collection
        collection_name = "test_round_trip_simple"
        if db.has_collection(collection_name):
            db.delete_collection(collection_name)
        
        collection = db.create_collection(collection_name)
        
        # Insert test data
        test_docs = [
            {
                "_key": "doc1",
                "name": "Acme Corporation",
                "address": "123 Main Street",
                "city": "Boston",
                "state": "MA"
            },
            {
                "_key": "doc2",
                "name": "Acme Corp",
                "address": "123 Main St",
                "city": "Boston",
                "state": "MA"
            },
            {
                "_key": "doc3",
                "name": "Beta Industries",
                "address": "456 Oak Avenue",
                "city": "New York",
                "state": "NY"
            },
        ]
        collection.insert_many(test_docs)
        print(f"✓ Inserted {len(test_docs)} test documents")
        
        # Test batch similarity
        service = BatchSimilarityService(
            db=db,
            collection=collection_name,
            field_weights={
                "name": 0.4,
                "address": 0.3,
                "city": 0.2,
                "state": 0.1
            },
            similarity_algorithm="jaro_winkler"
        )
        
        pairs = [("doc1", "doc2"), ("doc1", "doc3")]
        matches = service.compute_similarities(
            candidate_pairs=pairs,
            threshold=0.75
        )
        
        stats = service.get_statistics()
        
        print(f"✓ Pairs processed: {stats['pairs_processed']}")
        print(f"✓ Matches found: {len(matches)}")
        print(f"✓ Execution time: {stats['execution_time_seconds']:.3f}s")
        print(f"✓ Speed: {stats['pairs_per_second']:.0f} pairs/sec")
        
        for doc1, doc2, score in matches:
            print(f"  {doc1} <-> {doc2}: {score:.4f}")
        
        assert len(matches) >= 1, "Should find at least one match"
        assert stats['pairs_processed'] == 2
        
        # Cleanup
        db.delete_collection(collection_name)
        print("✓ Cleaned up test collection")
        print("✓ PASSED")
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("ROUND-TRIP TESTING - v3.0 Components")
    print("="*80)
    
    try:
        test_weighted_field_similarity()
        test_batch_similarity_service()
        
        print("\n" + "="*80)
        print("✓ ALL TESTS PASSED!")
        print("="*80)
        return 0
        
    except Exception as e:
        print("\n" + "="*80)
        print(f"✗ TESTS FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

