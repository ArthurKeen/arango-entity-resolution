"""
Tests for ANN Adapter Layer

Tests correctness of ANN adapter by comparing results with brute-force
on small datasets to ensure both methods produce equivalent results.
"""

import pytest
import numpy as np
from typing import List

from entity_resolution.similarity.ann_adapter import ANNAdapter


@pytest.fixture
def test_collection_name():
    """Collection name for testing"""
    return "test_ann_adapter"


@pytest.fixture
def setup_test_data(db_connection, test_collection_name):
    """Create test collection with sample data and embeddings"""
    collection_name = test_collection_name
    
    # Create collection if it doesn't exist
    if db_connection.has_collection(collection_name):
        db_connection.delete_collection(collection_name)
    
    collection = db_connection.create_collection(collection_name)
    
    # Insert test documents with known similarity patterns
    test_docs = [
        {
            '_key': 'doc1',
            'name': 'John Smith',
            'company': 'Acme Corporation',
            'city': 'New York',
            'category': 'A'
        },
        {
            '_key': 'doc2',
            'name': 'John R Smith',  # Similar to doc1
            'company': 'Acme Corp',  # Similar to doc1
            'city': 'New York',
            'category': 'A'
        },
        {
            '_key': 'doc3',
            'name': 'Jane Doe',
            'company': 'TechCo Inc',
            'city': 'San Francisco',
            'category': 'B'
        },
        {
            '_key': 'doc4',
            'name': 'Jane M Doe',  # Similar to doc3
            'company': 'TechCo Incorporated',  # Similar to doc3
            'city': 'San Francisco',
            'category': 'B'
        },
        {
            '_key': 'doc5',
            'name': 'Robert Johnson',
            'company': 'Global Enterprises',
            'city': 'Chicago',
            'category': 'C'
        },
        {
            '_key': 'doc6',
            'name': 'Bob Johnson',  # Similar to doc5
            'company': 'Global Ent',  # Similar to doc5
            'city': 'Chicago',
            'category': 'C'
        }
    ]
    
    for doc in test_docs:
        collection.insert(doc)

    # Generate deterministic embeddings without external model downloads.
    rng = np.random.RandomState(42)
    dim = 384
    base_vectors = {
        "A": rng.normal(size=dim),
        "B": rng.normal(size=dim),
        "C": rng.normal(size=dim)
    }

    def normalize(vec: np.ndarray) -> List[float]:
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec.tolist()
        return (vec / norm).tolist()

    for doc in test_docs:
        base = base_vectors[doc["category"]]
        noise = rng.normal(scale=0.05, size=dim)
        embedding = normalize(base + noise)
        collection.update({"_key": doc["_key"], "embedding_vector": embedding})
    
    yield collection_name
    
    # Cleanup
    if db_connection.has_collection(collection_name):
        db_connection.delete_collection(collection_name)


class TestANNAdapterInit:
    """Test ANNAdapter initialization"""
    
    def test_init_default(self, db_connection, setup_test_data):
        """Test initialization with default parameters"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data
        )
        
        assert adapter.collection == setup_test_data
        assert adapter.embedding_field == 'embedding_vector'
        assert adapter.method in ['arango_vector_search', 'brute_force']
        assert not adapter.force_brute_force
    
    def test_init_force_brute_force(self, db_connection, setup_test_data):
        """Test initialization with force_brute_force=True"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        assert adapter.method == 'brute_force'
        assert adapter.force_brute_force
    
    def test_init_custom_embedding_field(self, db_connection, setup_test_data):
        """Test initialization with custom embedding field"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            embedding_field='custom_embedding'
        )
        
        assert adapter.embedding_field == 'custom_embedding'


class TestANNAdapterCorrectness:
    """Test correctness of ANN adapter vs brute-force"""
    
    def test_find_similar_vectors_single_query(self, db_connection, setup_test_data):
        """Test finding similar vectors for a single query"""
        # Create adapter with brute-force (for comparison)
        adapter_bf = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        # Create adapter with auto-detection
        adapter_auto = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=False
        )
        
        # Get query vector from doc1
        collection = db_connection.collection(setup_test_data)
        doc1 = collection.get('doc1')
        query_vector = doc1['embedding_vector']
        
        # Find similar vectors with both methods
        results_bf = adapter_bf.find_similar_vectors(
            query_vector=query_vector,
            similarity_threshold=0.5,
            limit=10
        )
        
        results_auto = adapter_auto.find_similar_vectors(
            query_vector=query_vector,
            similarity_threshold=0.5,
            limit=10
        )
        
        # Both should return results
        assert len(results_bf) > 0
        assert len(results_auto) > 0
        
        # Results should be similar (may differ slightly due to method differences)
        # But top results should match
        bf_keys = {r['doc_key'] for r in results_bf[:3]}
        auto_keys = {r['doc_key'] for r in results_auto[:3]}
        
        # At least some overlap in top results
        assert len(bf_keys & auto_keys) > 0
    
    def test_find_similar_vectors_with_doc_key(self, db_connection, setup_test_data):
        """Test finding similar vectors using document key"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        # Find similar to doc1
        results = adapter.find_similar_vectors(
            query_doc_key='doc1',
            similarity_threshold=0.5,
            limit=10,
            exclude_self=True
        )
        
        assert len(results) > 0
        assert 'doc1' not in {r['doc_key'] for r in results}
        assert all(r['similarity'] >= 0.5 for r in results)
        assert all('doc_key' in r for r in results)
        assert all('similarity' in r for r in results)
        assert all('method' in r for r in results)
    
    def test_find_similar_vectors_blocking_field(self, db_connection, setup_test_data):
        """Test finding similar vectors with blocking field"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        collection = db_connection.collection(setup_test_data)
        doc1 = collection.get('doc1')
        query_vector = doc1['embedding_vector']
        
        # Find similar within same category
        results = adapter.find_similar_vectors(
            query_vector=query_vector,
            similarity_threshold=0.5,
            limit=10,
            blocking_field='category',
            blocking_value='A'
        )
        
        # All results should be in category A
        for result in results:
            doc = collection.get(result['doc_key'])
            assert doc['category'] == 'A'
    
    def test_find_all_pairs_correctness(self, db_connection, setup_test_data):
        """Test find_all_pairs correctness vs brute-force"""
        # Create two adapters: one forced brute-force, one auto
        adapter_bf = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        adapter_auto = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=False
        )
        
        # Find all pairs with both methods
        pairs_bf = adapter_bf.find_all_pairs(
            similarity_threshold=0.5,
            limit_per_entity=10
        )
        
        pairs_auto = adapter_auto.find_all_pairs(
            similarity_threshold=0.5,
            limit_per_entity=10
        )
        
        # Both should return pairs
        assert len(pairs_bf) > 0
        assert len(pairs_auto) > 0
        
        # Check structure
        for pair in pairs_bf + pairs_auto:
            assert 'doc1_key' in pair
            assert 'doc2_key' in pair
            assert 'similarity' in pair
            assert 'method' in pair
            assert pair['similarity'] >= 0.5
        
        # Convert to sets for comparison (ignore order)
        pairs_bf_set = {
            (min(p['doc1_key'], p['doc2_key']), max(p['doc1_key'], p['doc2_key']))
            for p in pairs_bf
        }
        pairs_auto_set = {
            (min(p['doc1_key'], p['doc2_key']), max(p['doc1_key'], p['doc2_key']))
            for p in pairs_auto
        }
        
        # Should have significant overlap (at least 50% of smaller set)
        overlap = len(pairs_bf_set & pairs_auto_set)
        min_size = min(len(pairs_bf_set), len(pairs_auto_set))
        overlap_ratio = overlap / min_size if min_size > 0 else 0
        
        assert overlap_ratio >= 0.5, (
            f"Overlap too low: {overlap}/{min_size} = {overlap_ratio:.2%}"
        )
    
    def test_find_all_pairs_blocking_field(self, db_connection, setup_test_data):
        """Test find_all_pairs with blocking field"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        # Find pairs within same category
        pairs = adapter.find_all_pairs(
            similarity_threshold=0.5,
            limit_per_entity=10,
            blocking_field='category'
        )
        
        # Verify all pairs are within same category
        collection = db_connection.collection(setup_test_data)
        for pair in pairs:
            doc1 = collection.get(pair['doc1_key'])
            doc2 = collection.get(pair['doc2_key'])
            assert doc1['category'] == doc2['category']
    
    def test_similarity_scores_consistent(self, db_connection, setup_test_data):
        """Test that similarity scores are consistent between methods"""
        adapter_bf = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        adapter_auto = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=False
        )
        
        collection = db_connection.collection(setup_test_data)
        doc1 = collection.get('doc1')
        query_vector = doc1['embedding_vector']
        
        # Get results from both methods
        results_bf = adapter_bf.find_similar_vectors(
            query_vector=query_vector,
            similarity_threshold=0.0,  # Get all results
            limit=100
        )
        
        results_auto = adapter_auto.find_similar_vectors(
            query_vector=query_vector,
            similarity_threshold=0.0,
            limit=100
        )
        
        # Create dictionaries keyed by doc_key for comparison
        bf_dict = {r['doc_key']: r['similarity'] for r in results_bf}
        auto_dict = {r['doc_key']: r['similarity'] for r in results_auto}
        
        # Check common documents have similar scores
        common_keys = set(bf_dict.keys()) & set(auto_dict.keys())
        assert len(common_keys) > 0
        
        for key in common_keys:
            bf_score = bf_dict[key]
            auto_score = auto_dict[key]
            
            # Scores should be very close (within 0.01 tolerance)
            # Note: May differ slightly due to floating point precision
            assert abs(bf_score - auto_score) < 0.01, (
                f"Score mismatch for {key}: brute_force={bf_score}, "
                f"auto={auto_score}, diff={abs(bf_score - auto_score)}"
            )
    
    def test_threshold_filtering(self, db_connection, setup_test_data):
        """Test that similarity threshold filtering works correctly"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        collection = db_connection.collection(setup_test_data)
        doc1 = collection.get('doc1')
        query_vector = doc1['embedding_vector']
        
        # Test with different thresholds
        for threshold in [0.3, 0.5, 0.7, 0.9]:
            results = adapter.find_similar_vectors(
                query_vector=query_vector,
                similarity_threshold=threshold,
                limit=100
            )
            
            # All results should meet threshold
            assert all(r['similarity'] >= threshold for r in results), (
                f"Threshold {threshold} not respected"
            )
            
            # Higher thresholds should return fewer or equal results
            if threshold > 0.3:
                prev_results = adapter.find_similar_vectors(
                    query_vector=query_vector,
                    similarity_threshold=threshold - 0.2,
                    limit=100
                )
                assert len(results) <= len(prev_results), (
                    f"Higher threshold {threshold} returned more results than lower"
                )
    
    def test_limit_enforcement(self, db_connection, setup_test_data):
        """Test that limit parameter is enforced"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        collection = db_connection.collection(setup_test_data)
        doc1 = collection.get('doc1')
        query_vector = doc1['embedding_vector']
        
        # Test with different limits
        for limit in [1, 5, 10, 20]:
            results = adapter.find_similar_vectors(
                query_vector=query_vector,
                similarity_threshold=0.0,
                limit=limit
            )
            
            assert len(results) <= limit, (
                f"Limit {limit} not respected, got {len(results)} results"
            )


class TestANNAdapterEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_collection(self, db_connection, temp_collection):
        """Test with empty collection"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=temp_collection,
            force_brute_force=True
        )
        
        results = adapter.find_similar_vectors(
            query_vector=[0.1, 0.2, 0.3],
            similarity_threshold=0.5,
            limit=10
        )
        
        assert len(results) == 0
    
    def test_missing_query_vector_and_key(self, db_connection, setup_test_data):
        """Test error when neither query_vector nor query_doc_key provided"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        with pytest.raises(ValueError, match="Either query_vector or query_doc_key"):
            adapter.find_similar_vectors(
                similarity_threshold=0.5,
                limit=10
            )
    
    def test_invalid_doc_key(self, db_connection, setup_test_data):
        """Test with invalid document key"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        results = adapter.find_similar_vectors(
            query_doc_key='nonexistent_doc',
            similarity_threshold=0.5,
            limit=10
        )
        
        assert len(results) == 0
    
    def test_zero_magnitude_vector(self, db_connection, setup_test_data):
        """Test handling of zero-magnitude vectors"""
        adapter = ANNAdapter(
            db=db_connection,
            collection=setup_test_data,
            force_brute_force=True
        )
        
        # Zero vector
        zero_vector = [0.0] * 384
        
        results = adapter.find_similar_vectors(
            query_vector=zero_vector,
            similarity_threshold=0.0,
            limit=10
        )
        
        # Should handle gracefully (may return empty or zero-similarity results)
        assert isinstance(results, list)
