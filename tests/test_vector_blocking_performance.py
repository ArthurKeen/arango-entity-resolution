"""
Performance baseline tests for Vector Blocking

Establishes performance baselines for vector embedding generation and
similarity-based blocking. These baselines serve as reference points for
future optimization work.

Run with: pytest tests/test_vector_blocking_performance.py -v -s
"""

import pytest
import time
import numpy as np
from typing import List, Dict

# Skip if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from entity_resolution.services.embedding_service import EmbeddingService
from entity_resolution.strategies import VectorBlockingStrategy


@pytest.fixture
def small_test_collection(db):
    """Create small test collection (100 documents)"""
    collection_name = "perf_test_small"
    
    if db.has_collection(collection_name):
        db.delete_collection(collection_name)
    
    collection = db.create_collection(collection_name)
    
    # Generate 100 test documents
    docs = []
    for i in range(100):
        docs.append({
            '_key': f'doc_{i:04d}',
            'name': f'Person {i}',
            'company': f'Company {i % 20}',  # 20 unique companies
            'city': f'City {i % 10}',        # 10 unique cities
            'description': f'This is a test document number {i} with some text content.'
        })
    
    for doc in docs:
        collection.insert(doc)
    
    yield collection_name
    
    if db.has_collection(collection_name):
        db.delete_collection(collection_name)


@pytest.fixture
def medium_test_collection(db):
    """Create medium test collection (1000 documents)"""
    collection_name = "perf_test_medium"
    
    if db.has_collection(collection_name):
        db.delete_collection(collection_name)
    
    collection = db.create_collection(collection_name)
    
    # Generate 1000 test documents
    docs = []
    for i in range(1000):
        docs.append({
            '_key': f'doc_{i:05d}',
            'name': f'Person {i}',
            'company': f'Company {i % 50}',   # 50 unique companies
            'city': f'City {i % 20}',         # 20 unique cities
            'description': f'Document {i} contains various information about entities and relationships.'
        })
    
    for doc in docs:
        collection.insert(doc)
    
    yield collection_name
    
    if db.has_collection(collection_name):
        db.delete_collection(collection_name)


class TestEmbeddingGenerationPerformance:
    """Performance baselines for embedding generation"""
    
    def test_single_embedding_generation(self):
        """Baseline: Single embedding generation time"""
        service = EmbeddingService(model_name='all-MiniLM-L6-v2', device='cpu')
        
        record = {
            'name': 'John Smith',
            'company': 'Acme Corporation',
            'description': 'A test record with various text fields.'
        }
        
        # Warmup
        _ = service.generate_embedding(record)
        
        # Measure
        iterations = 10
        start = time.time()
        for _ in range(iterations):
            embedding = service.generate_embedding(record)
        elapsed = time.time() - start
        
        avg_time = elapsed / iterations
        
        print(f"\n✓ Single embedding generation: {avg_time*1000:.2f} ms")
        print(f"  Throughput: {1/avg_time:.1f} embeddings/second")
        
        assert embedding.shape[0] == 384  # Verify dimension
        assert avg_time < 0.1  # Should be under 100ms per embedding
    
    def test_batch_embedding_generation_small(self, db, small_test_collection):
        """Baseline: Batch embedding generation (100 documents)"""
        service = EmbeddingService(model_name='all-MiniLM-L6-v2', device='cpu')
        
        collection = db.collection(small_test_collection)
        records = [doc for doc in collection.all()]
        
        # Measure
        start = time.time()
        embeddings = service.generate_embeddings_batch(
            records,
            text_fields=['name', 'company', 'description'],
            batch_size=32
        )
        elapsed = time.time() - start
        
        throughput = len(records) / elapsed
        
        print(f"\n✓ Batch embedding (100 docs): {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:.1f} docs/second")
        print(f"  Per-document: {elapsed/len(records)*1000:.2f} ms")
        
        assert embeddings.shape == (100, 384)
        assert throughput > 50  # Should process at least 50 docs/second on CPU
    
    def test_batch_embedding_generation_medium(self, db, medium_test_collection):
        """Baseline: Batch embedding generation (1000 documents)"""
        service = EmbeddingService(model_name='all-MiniLM-L6-v2', device='cpu')
        
        collection = db.collection(medium_test_collection)
        records = [doc for doc in collection.all()]
        
        # Measure
        start = time.time()
        embeddings = service.generate_embeddings_batch(
            records,
            text_fields=['name', 'company', 'description'],
            batch_size=32
        )
        elapsed = time.time() - start
        
        throughput = len(records) / elapsed
        
        print(f"\n✓ Batch embedding (1000 docs): {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:.1f} docs/second")
        print(f"  Per-document: {elapsed/len(records)*1000:.2f} ms")
        
        assert embeddings.shape == (1000, 384)
        assert throughput > 50  # Should process at least 50 docs/second
    
    def test_embedding_storage_performance(self, db, small_test_collection):
        """Baseline: Embedding storage time"""
        service = EmbeddingService(db_manager=None)
        service._embedding_dim = 384
        
        collection = db.collection(small_test_collection)
        records = [doc for doc in collection.all()]
        
        # Generate embeddings
        embeddings = np.random.rand(len(records), 384)
        
        # Measure storage time
        start = time.time()
        result = service.store_embeddings(
            small_test_collection,
            records,
            embeddings,
            database_name=db.name
        )
        elapsed = time.time() - start
        
        throughput = len(records) / elapsed
        
        print(f"\n✓ Embedding storage (100 docs): {elapsed:.2f} seconds")
        print(f"  Throughput: {throughput:.1f} docs/second")
        print(f"  Per-document: {elapsed/len(records)*1000:.2f} ms")
        
        assert result['updated'] == 100
        assert result['failed'] == 0
        assert throughput > 100  # Storage should be faster than generation


class TestVectorBlockingPerformance:
    """Performance baselines for vector blocking"""
    
    def test_vector_blocking_small(self, db, small_test_collection):
        """Baseline: Vector blocking on small collection (100 docs)"""
        # Setup: Generate embeddings first
        service = EmbeddingService()
        stats = service.ensure_embeddings_exist(
            small_test_collection,
            text_fields=['name', 'company', 'description'],
            database_name=db.name
        )
        
        assert stats['generated'] == 100
        
        # Measure vector blocking
        strategy = VectorBlockingStrategy(
            db=db,
            collection=small_test_collection,
            similarity_threshold=0.5,
            limit_per_entity=10
        )
        
        start = time.time()
        pairs = strategy.generate_candidates()
        elapsed = time.time() - start
        
        blocking_stats = strategy.get_statistics()
        
        print(f"\n✓ Vector blocking (100 docs): {elapsed:.2f} seconds")
        print(f"  Pairs found: {len(pairs)}")
        print(f"  Throughput: {100/elapsed:.1f} docs/second")
        print(f"  Avg time per doc: {elapsed/100*1000:.2f} ms")
        
        assert elapsed < 10  # Should complete within 10 seconds
        assert len(pairs) >= 0
    
    def test_vector_blocking_with_geographic_constraint(self, db, small_test_collection):
        """Baseline: Vector blocking with blocking field (geographic)"""
        # Setup embeddings
        service = EmbeddingService()
        service.ensure_embeddings_exist(
            small_test_collection,
            text_fields=['name', 'company'],
            database_name=db.name
        )
        
        # Measure with blocking field
        strategy = VectorBlockingStrategy(
            db=db,
            collection=small_test_collection,
            similarity_threshold=0.5,
            limit_per_entity=10,
            blocking_field='city'  # Geographic blocking
        )
        
        start = time.time()
        pairs = strategy.generate_candidates()
        elapsed = time.time() - start
        
        print(f"\n✓ Vector blocking with geographic constraint: {elapsed:.2f} seconds")
        print(f"  Pairs found: {len(pairs)}")
        print(f"  Speedup vs no constraint: TBD (compare with test above)")
        
        # Geographic blocking should reduce search space
        assert elapsed < 10
    
    def test_similarity_distribution_analysis(self, db, small_test_collection):
        """Baseline: Similarity distribution analysis performance"""
        # Setup embeddings
        service = EmbeddingService()
        service.ensure_embeddings_exist(
            small_test_collection,
            text_fields=['name', 'company'],
            database_name=db.name
        )
        
        strategy = VectorBlockingStrategy(
            db=db,
            collection=small_test_collection
        )
        
        # Measure distribution analysis
        start = time.time()
        stats = strategy.get_similarity_distribution(sample_size=50)
        elapsed = time.time() - start
        
        print(f"\n✓ Similarity distribution analysis: {elapsed:.2f} seconds")
        print(f"  Sample size: {stats['sample_size']}")
        print(f"  Mean similarity: {stats['mean_similarity']:.3f}")
        print(f"  Recommended threshold: {stats['recommended_thresholds']['balanced']:.3f}")
        
        assert elapsed < 5  # Should complete quickly
        assert 'mean_similarity' in stats


class TestEndToEndPerformance:
    """End-to-end performance baselines"""
    
    def test_complete_workflow_small(self, db, small_test_collection):
        """Baseline: Complete workflow (embed + block) on small dataset"""
        print(f"\n{'='*60}")
        print(f"COMPLETE WORKFLOW PERFORMANCE (100 documents)")
        print(f"{'='*60}")
        
        # Step 1: Embedding generation
        print("\nStep 1: Generating embeddings...")
        embedding_start = time.time()
        
        service = EmbeddingService()
        emb_stats = service.ensure_embeddings_exist(
            small_test_collection,
            text_fields=['name', 'company', 'description'],
            database_name=db.name
        )
        
        embedding_time = time.time() - embedding_start
        print(f"  ✓ Generated {emb_stats['generated']} embeddings in {embedding_time:.2f}s")
        print(f"  ✓ Throughput: {emb_stats['generated']/embedding_time:.1f} docs/second")
        
        # Step 2: Vector blocking
        print("\nStep 2: Vector blocking...")
        blocking_start = time.time()
        
        strategy = VectorBlockingStrategy(
            db=db,
            collection=small_test_collection,
            similarity_threshold=0.6,
            limit_per_entity=15
        )
        
        pairs = strategy.generate_candidates()
        blocking_time = time.time() - blocking_start
        
        print(f"  ✓ Found {len(pairs)} candidate pairs in {blocking_time:.2f}s")
        
        # Total time
        total_time = embedding_time + blocking_time
        
        print(f"\n{'='*60}")
        print(f"TOTAL TIME: {total_time:.2f} seconds")
        print(f"{'='*60}")
        print(f"  Embedding: {embedding_time:.2f}s ({embedding_time/total_time*100:.1f}%)")
        print(f"  Blocking:  {blocking_time:.2f}s ({blocking_time/total_time*100:.1f}%)")
        print(f"  Throughput: {100/total_time:.1f} docs/second (end-to-end)")
        
        assert total_time < 15  # Should complete within 15 seconds
        
        return {
            'total_docs': 100,
            'embedding_time': embedding_time,
            'blocking_time': blocking_time,
            'total_time': total_time,
            'pairs_found': len(pairs),
            'throughput': 100 / total_time
        }


class TestModelComparison:
    """Compare different embedding models"""
    
    def test_compare_models(self):
        """Baseline: Compare performance of different models"""
        models = ['all-MiniLM-L6-v2']  # Add more models as needed
        
        record = {
            'name': 'John Smith',
            'company': 'Acme Corporation',
            'description': 'Test record for model comparison.'
        }
        
        print(f"\n{'='*60}")
        print(f"MODEL COMPARISON")
        print(f"{'='*60}\n")
        print(f"{'Model':<25} {'Dim':<8} {'Time (ms)':<12} {'Throughput'}")
        print(f"{'-'*60}")
        
        for model_name in models:
            service = EmbeddingService(model_name=model_name, device='cpu')
            
            # Warmup
            _ = service.generate_embedding(record)
            
            # Measure
            iterations = 10
            start = time.time()
            for _ in range(iterations):
                embedding = service.generate_embedding(record)
            elapsed = time.time() - start
            
            avg_time = elapsed / iterations
            throughput = 1 / avg_time
            dim = embedding.shape[0]
            
            print(f"{model_name:<25} {dim:<8} {avg_time*1000:<12.2f} {throughput:.1f}/s")


if __name__ == '__main__':
    # Run with verbose output
    pytest.main([__file__, '-v', '-s'])

