"""
Integration tests for VectorBlockingStrategy

Tests vector-based blocking with ArangoDB integration.
Requires a running ArangoDB instance and sentence-transformers.
"""

import pytest
import numpy as np
from typing import List, Dict, Any

# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from entity_resolution.strategies import VectorBlockingStrategy
from entity_resolution.services.embedding_service import EmbeddingService


@pytest.fixture
def test_collection_name():
    """Collection name for testing"""
    return "test_vector_blocking"


@pytest.fixture
def setup_test_data(db, test_collection_name):
    """Create test collection with sample data"""
    # Create collection if it doesn't exist
    if not db.has_collection(test_collection_name):
        db.create_collection(test_collection_name)
    
    collection = db.collection(test_collection_name)
    
    # Clear any existing data
    collection.truncate()
    
    # Insert test documents (similar pairs for testing)
    test_docs = [
        {
            '_key': 'doc1',
            'name': 'John Smith',
            'company': 'Acme Corporation',
            'city': 'New York'
        },
        {
            '_key': 'doc2',
            'name': 'John R Smith',
            'company': 'Acme Corp',
            'city': 'New York'
        },
        {
            '_key': 'doc3',
            'name': 'Jane Doe',
            'company': 'TechCo Inc',
            'city': 'San Francisco'
        },
        {
            '_key': 'doc4',
            'name': 'Jane M Doe',
            'company': 'TechCo Incorporated',
            'city': 'San Francisco'
        },
        {
            '_key': 'doc5',
            'name': 'Robert Johnson',
            'company': 'Global Enterprises',
            'city': 'Chicago'
        }
    ]
    
    for doc in test_docs:
        collection.insert(doc)
    
    yield test_docs
    
    # Cleanup
    if db.has_collection(test_collection_name):
        db.delete_collection(test_collection_name)


@pytest.fixture
def setup_embeddings(db, test_collection_name, setup_test_data):
    """Generate embeddings for test data"""
    embedding_service = EmbeddingService(
        model_name='all-MiniLM-L6-v2',
        device='cpu'
    )
    
    # Generate embeddings
    stats = embedding_service.ensure_embeddings_exist(
        test_collection_name,
        text_fields=['name', 'company', 'city'],
        database_name=db.name
    )
    
    return stats


class TestVectorBlockingStrategyInit:
    """Test VectorBlockingStrategy initialization"""
    
    def test_init_default_params(self, db, test_collection_name):
        """Test initialization with default parameters"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name
        )
        
        assert strategy.embedding_field == 'embedding_vector'
        assert strategy.similarity_threshold == 0.7
        assert strategy.limit_per_entity == 20
        assert strategy.blocking_field is None
    
    def test_init_custom_params(self, db, test_collection_name):
        """Test initialization with custom parameters"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            embedding_field='custom_embedding',
            similarity_threshold=0.85,
            limit_per_entity=10,
            blocking_field='city'
        )
        
        assert strategy.embedding_field == 'custom_embedding'
        assert strategy.similarity_threshold == 0.85
        assert strategy.limit_per_entity == 10
        assert strategy.blocking_field == 'city'
    
    def test_init_invalid_threshold(self, db, test_collection_name):
        """Test validation of similarity_threshold"""
        # Too low
        with pytest.raises(ValueError, match="similarity_threshold"):
            VectorBlockingStrategy(
                db=db,
                collection=test_collection_name,
                similarity_threshold=-0.1
            )
        
        # Too high
        with pytest.raises(ValueError, match="similarity_threshold"):
            VectorBlockingStrategy(
                db=db,
                collection=test_collection_name,
                similarity_threshold=1.5
            )
    
    def test_init_invalid_limit(self, db, test_collection_name):
        """Test validation of limit_per_entity"""
        with pytest.raises(ValueError, match="limit_per_entity"):
            VectorBlockingStrategy(
                db=db,
                collection=test_collection_name,
                limit_per_entity=0
            )


class TestCheckEmbeddingsExist:
    """Test _check_embeddings_exist method"""
    
    def test_check_with_embeddings(self, db, test_collection_name, setup_embeddings):
        """Test checking embeddings when they exist"""
        strategy = VectorBlockingStrategy(db=db, collection=test_collection_name)
        
        stats = strategy._check_embeddings_exist()
        
        assert stats['total'] == 5
        assert stats['with_embeddings'] == 5
        assert stats['without_embeddings'] == 0
        assert stats['coverage_percent'] == 100.0
    
    def test_check_without_embeddings(self, db, test_collection_name, setup_test_data):
        """Test checking embeddings when they don't exist"""
        strategy = VectorBlockingStrategy(db=db, collection=test_collection_name)
        
        stats = strategy._check_embeddings_exist()
        
        assert stats['total'] == 5
        assert stats['with_embeddings'] == 0
        assert stats['without_embeddings'] == 5
        assert stats['coverage_percent'] == 0.0
    
    def test_check_partial_embeddings(self, db, test_collection_name, setup_test_data):
        """Test checking when only some documents have embeddings"""
        # Add embeddings to only 2 documents
        collection = db.collection(test_collection_name)
        collection.update({'_key': 'doc1', 'embedding_vector': [0.1, 0.2, 0.3]})
        collection.update({'_key': 'doc2', 'embedding_vector': [0.2, 0.3, 0.4]})
        
        strategy = VectorBlockingStrategy(db=db, collection=test_collection_name)
        stats = strategy._check_embeddings_exist()
        
        assert stats['total'] == 5
        assert stats['with_embeddings'] == 2
        assert stats['without_embeddings'] == 3
        assert stats['coverage_percent'] == 40.0


class TestGenerateCandidates:
    """Test generate_candidates method"""
    
    def test_generate_candidates_basic(self, db, test_collection_name, setup_embeddings):
        """Test basic candidate generation with vector similarity"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.5,  # Lower threshold for testing
            limit_per_entity=10
        )
        
        pairs = strategy.generate_candidates()
        
        # Should find some candidates
        assert len(pairs) > 0
        
        # Check pair format
        for pair in pairs:
            assert 'doc1_key' in pair
            assert 'doc2_key' in pair
            assert 'similarity' in pair
            assert 'method' in pair
            assert pair['method'] == 'vector'
            
            # Check similarity is in valid range
            assert 0 <= pair['similarity'] <= 1
            
            # Check keys are normalized (doc1 < doc2)
            assert pair['doc1_key'] < pair['doc2_key']
    
    def test_generate_candidates_high_threshold(self, db, test_collection_name, setup_embeddings):
        """Test candidate generation with high similarity threshold"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.95  # Very high threshold
        )
        
        pairs = strategy.generate_candidates()
        
        # With high threshold, should find fewer or no candidates
        # All found pairs should have high similarity
        for pair in pairs:
            assert pair['similarity'] >= 0.95
    
    def test_generate_candidates_with_blocking_field(self, db, test_collection_name, setup_embeddings):
        """Test candidate generation with geographic blocking"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.5,
            blocking_field='city'  # Only compare within same city
        )
        
        pairs = strategy.generate_candidates()
        
        # Verify blocking field constraint
        collection = db.collection(test_collection_name)
        for pair in pairs:
            doc1 = collection.get(pair['doc1_key'])
            doc2 = collection.get(pair['doc2_key'])
            
            # Both documents should have the same city
            assert doc1['city'] == doc2['city']
    
    def test_generate_candidates_with_filters(self, db, test_collection_name, setup_embeddings):
        """Test candidate generation with field filters"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.5,
            filters={
                'name': {'not_null': True, 'min_length': 5}
            }
        )
        
        pairs = strategy.generate_candidates()
        
        # Should only include documents matching filters
        collection = db.collection(test_collection_name)
        for pair in pairs:
            doc1 = collection.get(pair['doc1_key'])
            doc2 = collection.get(pair['doc2_key'])
            
            assert doc1['name'] is not None
            assert len(doc1['name']) >= 5
            assert doc2['name'] is not None
            assert len(doc2['name']) >= 5
    
    def test_generate_candidates_no_embeddings(self, db, test_collection_name, setup_test_data):
        """Test error when no embeddings exist"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name
        )
        
        with pytest.raises(RuntimeError, match="No embeddings found"):
            strategy.generate_candidates()
    
    def test_generate_candidates_limit_per_entity(self, db, test_collection_name, setup_embeddings):
        """Test that limit_per_entity is respected"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.0,  # Match everything
            limit_per_entity=1  # Only 1 candidate per entity
        )
        
        pairs = strategy.generate_candidates()
        
        # Count candidates per document
        from collections import Counter
        doc1_counts = Counter(p['doc1_key'] for p in pairs)
        
        # No document should have more than limit_per_entity candidates
        for count in doc1_counts.values():
            assert count <= 1
    
    def test_generate_candidates_statistics(self, db, test_collection_name, setup_embeddings):
        """Test that statistics are properly tracked"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.5
        )
        
        pairs = strategy.generate_candidates()
        stats = strategy.get_statistics()
        
        assert stats['total_pairs'] == len(pairs)
        assert stats['execution_time_seconds'] > 0
        assert stats['strategy_name'] == 'VectorBlockingStrategy'
        assert 'timestamp' in stats
        assert stats['embedding_field'] == 'embedding_vector'
        assert stats['similarity_threshold'] == 0.5
        assert stats['embedding_coverage_percent'] == 100.0


class TestGetSimilarityDistribution:
    """Test get_similarity_distribution method"""
    
    def test_similarity_distribution_basic(self, db, test_collection_name, setup_embeddings):
        """Test basic similarity distribution analysis"""
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name
        )
        
        stats = strategy.get_similarity_distribution(sample_size=10)
        
        assert 'sample_size' in stats
        assert 'min_similarity' in stats
        assert 'max_similarity' in stats
        assert 'mean_similarity' in stats
        assert 'median_similarity' in stats
        assert 'std_similarity' in stats
        assert 'distribution' in stats
        assert 'recommended_thresholds' in stats
        
        # Check recommended thresholds
        thresholds = stats['recommended_thresholds']
        assert 'conservative' in thresholds
        assert 'balanced' in thresholds
        assert 'aggressive' in thresholds
        
        # Conservative should be >= balanced >= aggressive
        assert thresholds['conservative'] >= thresholds['balanced']
        assert thresholds['balanced'] >= thresholds['aggressive']
    
    def test_similarity_distribution_empty_collection(self, db, test_collection_name):
        """Test similarity distribution on empty collection"""
        # Create empty collection
        if not db.has_collection(test_collection_name):
            db.create_collection(test_collection_name)
        
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name
        )
        
        stats = strategy.get_similarity_distribution(sample_size=10)
        
        assert 'error' in stats
        
        # Cleanup
        db.delete_collection(test_collection_name)


class TestVectorBlockingIntegration:
    """Integration tests for full vector blocking workflow"""
    
    def test_full_workflow(self, db, test_collection_name, setup_test_data):
        """Test complete workflow: embed → block → verify"""
        # Step 1: Generate embeddings
        embedding_service = EmbeddingService()
        emb_stats = embedding_service.ensure_embeddings_exist(
            test_collection_name,
            text_fields=['name', 'company'],
            database_name=db.name
        )
        
        assert emb_stats['generated'] == 5
        
        # Step 2: Generate candidates with vector blocking
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.6
        )
        
        pairs = strategy.generate_candidates()
        
        # Step 3: Verify similar pairs are found
        # doc1 and doc2 should be similar (John Smith variants)
        # doc3 and doc4 should be similar (Jane Doe variants)
        pair_keys = {(p['doc1_key'], p['doc2_key']) for p in pairs}
        
        # Check that at least some expected similar pairs are found
        assert len(pairs) > 0
        
        # Verify similarity scores make sense
        for pair in pairs:
            assert pair['similarity'] >= 0.6
    
    def test_comparison_with_exact_blocking(self, db, test_collection_name, setup_embeddings):
        """Test that vector blocking finds fuzzy matches exact blocking misses"""
        from entity_resolution.strategies import CollectBlockingStrategy
        
        # Exact blocking (Tier 1) - requires exact field matches
        exact_strategy = CollectBlockingStrategy(
            db=db,
            collection=test_collection_name,
            blocking_fields=['company']  # Exact company match
        )
        
        exact_pairs = exact_strategy.generate_candidates()
        
        # Vector blocking (Tier 3) - semantic similarity
        vector_strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.6
        )
        
        vector_pairs = vector_strategy.generate_candidates()
        
        # Vector blocking should find similar but not identical records
        # (e.g., "Acme Corporation" vs "Acme Corp")
        assert len(vector_pairs) >= len(exact_pairs)
    
    def test_multi_tier_blocking(self, db, test_collection_name, setup_embeddings):
        """Test combining vector blocking with other tiers"""
        # Tier 1: Exact blocking
        from entity_resolution.strategies import CollectBlockingStrategy
        
        tier1 = CollectBlockingStrategy(
            db=db,
            collection=test_collection_name,
            blocking_fields=['city']
        )
        
        # Tier 3: Vector blocking
        tier3 = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.7
        )
        
        # Combine results
        tier1_pairs = tier1.generate_candidates()
        tier3_pairs = tier3.generate_candidates()
        
        # Combine and deduplicate
        all_pairs = {}
        for pair in tier1_pairs + tier3_pairs:
            key = (pair['doc1_key'], pair['doc2_key'])
            if key not in all_pairs or pair.get('similarity', 0) > all_pairs[key].get('similarity', 0):
                all_pairs[key] = pair
        
        combined_pairs = list(all_pairs.values())
        
        # Combined should have at least as many as either individual tier
        assert len(combined_pairs) >= len(tier1_pairs)
        assert len(combined_pairs) >= len(tier3_pairs)


class TestVectorBlockingEdgeCases:
    """Test edge cases and error handling"""
    
    def test_single_document_with_embedding(self, db, test_collection_name):
        """Test with only one document"""
        if not db.has_collection(test_collection_name):
            db.create_collection(test_collection_name)
        
        collection = db.collection(test_collection_name)
        collection.truncate()
        
        # Insert one document with embedding
        collection.insert({
            '_key': 'only_doc',
            'name': 'Single Doc',
            'embedding_vector': [0.1, 0.2, 0.3]
        })
        
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.5
        )
        
        pairs = strategy.generate_candidates()
        
        # Should return empty list (no pairs possible with 1 doc)
        assert len(pairs) == 0
        
        # Cleanup
        db.delete_collection(test_collection_name)
    
    def test_identical_embeddings(self, db, test_collection_name):
        """Test with documents having identical embeddings"""
        if not db.has_collection(test_collection_name):
            db.create_collection(test_collection_name)
        
        collection = db.collection(test_collection_name)
        collection.truncate()
        
        # Insert documents with identical embeddings
        identical_embedding = [0.5, 0.5, 0.5]
        for i in range(3):
            collection.insert({
                '_key': f'doc{i}',
                'name': f'Document {i}',
                'embedding_vector': identical_embedding
            })
        
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.99
        )
        
        pairs = strategy.generate_candidates()
        
        # All pairs should have similarity = 1.0
        assert len(pairs) > 0
        for pair in pairs:
            assert pair['similarity'] >= 0.99
        
        # Cleanup
        db.delete_collection(test_collection_name)
    
    def test_different_embedding_dimensions(self, db, test_collection_name):
        """Test handling of documents with different embedding dimensions"""
        if not db.has_collection(test_collection_name):
            db.create_collection(test_collection_name)
        
        collection = db.collection(test_collection_name)
        collection.truncate()
        
        # Insert documents with different dimension embeddings
        collection.insert({
            '_key': 'doc1',
            'name': 'Doc 1',
            'embedding_vector': [0.1, 0.2, 0.3]  # 3-dim
        })
        collection.insert({
            '_key': 'doc2',
            'name': 'Doc 2',
            'embedding_vector': [0.1, 0.2]  # 2-dim (different!)
        })
        
        strategy = VectorBlockingStrategy(
            db=db,
            collection=test_collection_name,
            similarity_threshold=0.5
        )
        
        # Should handle gracefully (may fail or skip mismatched pairs)
        # We don't assert specific behavior, just that it doesn't crash
        try:
            pairs = strategy.generate_candidates()
        except Exception as e:
            # Expected to fail due to dimension mismatch
            assert 'dimension' in str(e).lower() or 'length' in str(e).lower()
        
        # Cleanup
        db.delete_collection(test_collection_name)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

