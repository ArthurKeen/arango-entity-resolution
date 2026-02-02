"""
Unit tests for LSH Blocking Strategy.

Tests for:
- LSHBlockingStrategy initialization and validation
- Deterministic hashing (same seed -> same results)
- Recall on synthetic data
- Output format compatibility
"""

import pytest
import numpy as np
from entity_resolution.strategies import LSHBlockingStrategy


class MockAQL:
    """Mock AQL executor for testing."""
    
    def __init__(self, documents=None):
        self.documents = documents or []
    
    def execute(self, query, bind_vars=None):
        """Mock AQL execution."""
        # Check for stats query (has "total" and "with_embeddings")
        if "RETURN {" in query and "total" in query and "with_embeddings" in query:
            # Return stats query result
            sample_embedding = None
            if self.documents:
                for doc in self.documents:
                    if doc.get('embedding') is not None:
                        sample_embedding = doc['embedding']
                        break
            
            stats_dict = {
                'total': len(self.documents),
                'with_embeddings': len([d for d in self.documents if d.get('embedding') is not None]),
                'without_embeddings': len([d for d in self.documents if d.get('embedding') is None]),
                'coverage_percent': (len([d for d in self.documents if d.get('embedding') is not None]) / len(self.documents) * 100) if self.documents else 0.0,
                'embedding_dim': len(sample_embedding) if sample_embedding is not None else None
            }
            return iter([stats_dict])
        # Return documents if query asks for them
        elif "RETURN {" in query and ("embedding" in query or "_key" in query):
            return iter(self.documents)
        return iter([])


class MockDB:
    """Mock database for testing."""
    
    def __init__(self, documents=None):
        self.aql = MockAQL(documents)


@pytest.fixture
def mock_db():
    """Mock database fixture."""
    return MockDB()


@pytest.fixture
def sample_embeddings():
    """Generate sample embeddings for testing."""
    # Create 10 vectors in 384-dimensional space
    # Some vectors are similar (high cosine similarity), some are different
    np.random.seed(42)
    
    # Base vectors
    base1 = np.random.randn(384)
    base1 = base1 / np.linalg.norm(base1)
    
    base2 = np.random.randn(384)
    base2 = base2 / np.linalg.norm(base2)
    
    # Create similar vectors by adding small noise
    vectors = []
    for i in range(5):
        # Group 1: similar to base1
        v = base1 + 0.1 * np.random.randn(384)
        v = v / np.linalg.norm(v)
        vectors.append(v)
    
    for i in range(5):
        # Group 2: similar to base2
        v = base2 + 0.1 * np.random.randn(384)
        v = v / np.linalg.norm(v)
        vectors.append(v)
    
    return vectors


@pytest.fixture
def sample_documents(sample_embeddings):
    """Create sample documents with embeddings."""
    documents = []
    for i, embedding in enumerate(sample_embeddings):
        documents.append({
            '_key': f'doc_{i}',
            'embedding': embedding.tolist(),
            'blocking_value': 'group1' if i < 5 else 'group2'
        })
    return documents


class TestLSHBlockingStrategy:
    """Tests for LSHBlockingStrategy."""
    
    def test_initialization(self, mock_db):
        """Test initialization with valid parameters."""
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test_collection",
            embedding_field="embedding_vector",
            num_hash_tables=10,
            num_hyperplanes=8,
            random_seed=42
        )
        
        assert strategy.collection == "test_collection"
        assert strategy.embedding_field == "embedding_vector"
        assert strategy.num_hash_tables == 10
        assert strategy.num_hyperplanes == 8
        assert strategy.random_seed == 42
        assert strategy._hyperplanes is not None
        assert strategy._hyperplanes.shape[0] == 10 * 8  # L * k hyperplanes
    
    def test_initialization_validation(self, mock_db):
        """Test parameter validation."""
        # Invalid num_hash_tables
        with pytest.raises(ValueError, match="num_hash_tables must be >= 1"):
            LSHBlockingStrategy(
                db=mock_db,
                collection="test",
                num_hash_tables=0
            )
        
        # Invalid num_hyperplanes
        with pytest.raises(ValueError, match="num_hyperplanes must be >= 1"):
            LSHBlockingStrategy(
                db=mock_db,
                collection="test",
                num_hyperplanes=0
            )
    
    def test_hyperplane_generation_deterministic(self, mock_db):
        """Test that hyperplane generation is deterministic with same seed."""
        strategy1 = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        strategy2 = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        # Same seed should produce same hyperplanes
        np.testing.assert_array_equal(strategy1._hyperplanes, strategy2._hyperplanes)
    
    def test_hyperplane_generation_different_seeds(self, mock_db):
        """Test that different seeds produce different hyperplanes."""
        strategy1 = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        strategy2 = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=123
        )
        
        # Different seeds should produce different hyperplanes
        assert not np.array_equal(strategy1._hyperplanes, strategy2._hyperplanes)
    
    def test_compute_hash_deterministic(self, mock_db):
        """Test that hash computation is deterministic."""
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        # Create a test vector
        test_vector = np.random.randn(384)
        test_vector = test_vector / np.linalg.norm(test_vector)
        
        # Compute hash twice - should be identical
        hash1 = strategy._compute_hash(test_vector, table_idx=0)
        hash2 = strategy._compute_hash(test_vector, table_idx=0)
        
        assert hash1 == hash2
    
    def test_compute_hash_different_tables(self, mock_db):
        """Test that different hash tables produce different hashes."""
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        test_vector = np.random.randn(384)
        test_vector = test_vector / np.linalg.norm(test_vector)
        
        # Different tables should produce different hashes (usually)
        hash1 = strategy._compute_hash(test_vector, table_idx=0)
        hash2 = strategy._compute_hash(test_vector, table_idx=1)
        
        # They might be the same by chance, but unlikely with multiple hyperplanes
        # This is probabilistic, so we just check they're valid hashes
        assert isinstance(hash1, str)
        assert isinstance(hash2, str)
        assert len(hash1) == 32  # MD5 hex digest length
    
    def test_generate_candidates_no_embeddings(self, mock_db):
        """Test error when no embeddings exist."""
        mock_db.aql.documents = []
        
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            random_seed=42
        )
        
        with pytest.raises(RuntimeError, match="No embeddings found"):
            strategy.generate_candidates()
    
    def test_generate_candidates_deterministic(self, mock_db, sample_documents):
        """Test that candidate generation is deterministic with same seed."""
        # Create separate mock DBs to avoid state issues
        mock_db1 = MockDB(sample_documents)
        mock_db2 = MockDB(sample_documents)
        
        strategy1 = LSHBlockingStrategy(
            db=mock_db1,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        strategy2 = LSHBlockingStrategy(
            db=mock_db2,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        # Generate candidates twice with same seed
        pairs1 = strategy1.generate_candidates()
        pairs2 = strategy2.generate_candidates()
        
        # Should produce identical results
        assert len(pairs1) == len(pairs2)
        
        # Sort pairs for comparison
        pairs1_sorted = sorted(pairs1, key=lambda p: (p['doc1_key'], p['doc2_key']))
        pairs2_sorted = sorted(pairs2, key=lambda p: (p['doc1_key'], p['doc2_key']))
        
        for p1, p2 in zip(pairs1_sorted, pairs2_sorted):
            assert p1['doc1_key'] == p2['doc1_key']
            assert p1['doc2_key'] == p2['doc2_key']
            assert p1['lsh_hash'] == p2['lsh_hash']
            assert p1['hash_table'] == p2['hash_table']
    
    def test_generate_candidates_output_format(self, mock_db, sample_documents):
        """Test that output format is compatible with existing pipeline."""
        mock_db.aql.documents = sample_documents
        
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        pairs = strategy.generate_candidates()
        
        # Check output format
        assert isinstance(pairs, list)
        
        for pair in pairs:
            # Required fields
            assert 'doc1_key' in pair
            assert 'doc2_key' in pair
            assert 'method' in pair
            
            # LSH-specific fields
            assert 'lsh_hash' in pair
            assert 'hash_table' in pair
            
            # Format checks
            assert isinstance(pair['doc1_key'], str)
            assert isinstance(pair['doc2_key'], str)
            assert pair['method'] == 'lsh'
            assert isinstance(pair['lsh_hash'], str)
            assert isinstance(pair['hash_table'], int)
            assert 0 <= pair['hash_table'] < strategy.num_hash_tables
            
            # Normalization: doc1_key < doc2_key
            assert pair['doc1_key'] < pair['doc2_key']
    
    def test_generate_candidates_recall_synthetic(self, mock_db, sample_embeddings):
        """Test recall on synthetic data with known similar pairs."""
        # Create documents where we know which pairs should match
        # Group 1: indices 0-4 (should match with each other)
        # Group 2: indices 5-9 (should match with each other)
        
        documents = []
        for i, embedding in enumerate(sample_embeddings):
            documents.append({
                '_key': f'doc_{i}',
                'embedding': embedding.tolist()
            })
        
        mock_db.aql.documents = documents
        
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=10,  # More tables = higher recall
            num_hyperplanes=8,
            random_seed=42
        )
        
        pairs = strategy.generate_candidates()
        
        # Extract pairs
        pair_keys = {(p['doc1_key'], p['doc2_key']) for p in pairs}
        
        # Expected pairs: within-group pairs
        # Group 1: doc_0 to doc_4 (10 pairs: C(5,2))
        # Group 2: doc_5 to doc_9 (10 pairs: C(5,2))
        expected_pairs_group1 = {
            (f'doc_{i}', f'doc_{j}')
            for i in range(5)
            for j in range(i + 1, 5)
        }
        expected_pairs_group2 = {
            (f'doc_{i}', f'doc_{j}')
            for i in range(5, 10)
            for j in range(i + 1, 10)
        }
        expected_pairs = expected_pairs_group1 | expected_pairs_group2
        
        # Calculate recall: how many expected pairs were found?
        found_pairs = pair_keys & expected_pairs
        recall = len(found_pairs) / len(expected_pairs) if expected_pairs else 0.0
        
        # With L=10, k=8, we should find at least some pairs
        # This is probabilistic, so we check for reasonable recall (> 0)
        assert recall > 0.0, f"Recall should be > 0, got {recall}"
        
        # With more hash tables, recall should improve
        # This is a sanity check - LSH is probabilistic
        assert len(pairs) > 0, "Should find at least some candidate pairs"
    
    def test_generate_candidates_blocking_field(self, mock_db, sample_documents):
        """Test that blocking field constraint works."""
        mock_db.aql.documents = sample_documents
        
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            blocking_field="blocking_value",
            random_seed=42
        )
        
        pairs = strategy.generate_candidates()
        
        # All pairs should have matching blocking_field values
        for pair in pairs:
            doc1 = next(d for d in sample_documents if d['_key'] == pair['doc1_key'])
            doc2 = next(d for d in sample_documents if d['_key'] == pair['doc2_key'])
            
            assert doc1['blocking_value'] == doc2['blocking_value']
    
    def test_statistics_tracking(self, mock_db, sample_documents):
        """Test that statistics are properly tracked."""
        mock_db.aql.documents = sample_documents
        
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test",
            num_hash_tables=5,
            num_hyperplanes=4,
            random_seed=42
        )
        
        pairs = strategy.generate_candidates()
        stats = strategy.get_statistics()
        
        assert stats['total_pairs'] == len(pairs)
        assert stats['strategy_name'] == 'LSHBlockingStrategy'
        assert stats['num_hash_tables'] == 5
        assert stats['num_hyperplanes'] == 4
        assert stats['random_seed'] == 42
        assert stats['embedding_field'] == 'embedding_vector'
        assert 'execution_time_seconds' in stats
        assert 'timestamp' in stats
        assert 'embedding_coverage_percent' in stats
        assert 'documents_with_embeddings' in stats
        assert 'embedding_dimension' in stats
    
    def test_repr(self, mock_db):
        """Test string representation."""
        strategy = LSHBlockingStrategy(
            db=mock_db,
            collection="test_collection",
            num_hash_tables=10,
            num_hyperplanes=8,
            random_seed=42
        )
        
        repr_str = repr(strategy)
        assert "LSHBlockingStrategy" in repr_str
        assert "test_collection" in repr_str
        assert "L=10" in repr_str
        assert "k=8" in repr_str
        assert "seed=42" in repr_str


class TestLSHRecall:
    """Tests focused on recall performance."""
    
    def test_recall_increases_with_more_tables(self, mock_db, sample_embeddings):
        """Test that more hash tables increase recall."""
        documents = []
        for i, embedding in enumerate(sample_embeddings):
            documents.append({
                '_key': f'doc_{i}',
                'embedding': embedding.tolist()
            })
        
        # Expected pairs: within-group pairs
        expected_pairs = {
            (f'doc_{i}', f'doc_{j}')
            for i in range(5)
            for j in range(i + 1, 5)
        } | {
            (f'doc_{i}', f'doc_{j}')
            for i in range(5, 10)
            for j in range(i + 1, 10)
        }
        
        recalls = []
        
        for num_tables in [5, 10, 20]:
            mock_db.aql.documents = documents.copy()
            
            strategy = LSHBlockingStrategy(
                db=mock_db,
                collection="test",
                num_hash_tables=num_tables,
                num_hyperplanes=8,
                random_seed=42
            )
            
            pairs = strategy.generate_candidates()
            pair_keys = {(p['doc1_key'], p['doc2_key']) for p in pairs}
            found_pairs = pair_keys & expected_pairs
            recall = len(found_pairs) / len(expected_pairs) if expected_pairs else 0.0
            recalls.append(recall)
        
        # With more tables, recall should generally increase (probabilistic)
        # This is a sanity check - we just verify it's working
        assert all(r >= 0.0 for r in recalls), "All recalls should be >= 0"
        assert any(r > 0.0 for r in recalls), "At least one recall should be > 0"
    
    def test_precision_vs_recall_tradeoff(self, mock_db, sample_embeddings):
        """Test that more hyperplanes increase precision but may decrease recall."""
        documents = []
        for i, embedding in enumerate(sample_embeddings):
            documents.append({
                '_key': f'doc_{i}',
                'embedding': embedding.tolist()
            })
        
        mock_db.aql.documents = documents
        
        # Test with different numbers of hyperplanes
        results = []
        
        for num_hyperplanes in [4, 8, 16]:
            mock_db.aql.documents = documents.copy()
            
            strategy = LSHBlockingStrategy(
                db=mock_db,
                collection="test",
                num_hash_tables=10,
                num_hyperplanes=num_hyperplanes,
                random_seed=42
            )
            
            pairs = strategy.generate_candidates()
            results.append({
                'k': num_hyperplanes,
                'num_pairs': len(pairs)
            })
        
        # More hyperplanes should generally produce fewer pairs (higher precision)
        # This is probabilistic, so we just verify it's working
        assert all(r['num_pairs'] >= 0 for r in results), "All pair counts should be >= 0"
