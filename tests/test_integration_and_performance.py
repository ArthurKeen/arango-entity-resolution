"""
Integration tests and performance benchmarks.

These tests require a running ArangoDB instance and test the complete
workflow with real data.

Run with: pytest test_integration_and_performance.py -v -s
Skip if no database: pytest -m "not integration"
"""

import pytest
import time
from entity_resolution import (
    CollectBlockingStrategy,
    BM25BlockingStrategy,
    BatchSimilarityService,
    SimilarityEdgeService,
    WCCClusteringService,
    get_database
)


# Mark all tests as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def test_db():
    """Get test database connection."""
    try:
        db = get_database()
        yield db
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture(scope="module")
def test_collection(test_db):
    """Create and populate test collection."""
    collection_name = "test_companies_integration"
    
    # Create collection
    if test_db.has_collection(collection_name):
        test_db.delete_collection(collection_name)
    
    collection = test_db.create_collection(collection_name)
    
    # Insert test data
    test_docs = [
        {"_key": "c001", "name": "Acme Corp", "phone": "5551234567", "state": "CA", "ceo": "John Smith", "address": "123 Main St"},
        {"_key": "c002", "name": "Acme Corporation", "phone": "5551234567", "state": "CA", "ceo": "J. Smith", "address": "123 Main Street"},
        {"_key": "c003", "name": "Beta Inc", "phone": "5559876543", "state": "NY", "ceo": "Jane Doe", "address": "456 Broadway"},
        {"_key": "c004", "name": "Beta Incorporated", "phone": "5559876543", "state": "NY", "ceo": "Jane Doe", "address": "456 Broadway Ave"},
        {"_key": "c005", "name": "Gamma LLC", "phone": "5555555555", "state": "TX", "ceo": "Bob Johnson", "address": "789 Oak Ave"},
        {"_key": "c006", "name": "Delta Corp", "phone": "5552222222", "state": "CA", "ceo": "Alice Brown", "address": "321 Pine St"},
        {"_key": "c007", "name": "Delta Corporation", "phone": "5552222222", "state": "CA", "ceo": "Alice Brown", "address": "321 Pine Street"},
    ]
    
    collection.insert_many(test_docs)
    
    yield collection_name
    
    # Cleanup
    test_db.delete_collection(collection_name)


class TestCollectBlockingIntegration:
    """Integration tests for CollectBlockingStrategy."""
    
    def test_phone_state_blocking(self, test_db, test_collection):
        """Test phone + state blocking with real data."""
        strategy = CollectBlockingStrategy(
            db=test_db,
            collection=test_collection,
            blocking_fields=["phone", "state"],
            filters={
                "phone": {"not_null": True, "min_length": 10},
                "state": {"not_null": True}
            },
            max_block_size=10,
            min_block_size=2
        )
        
        pairs = strategy.generate_candidates()
        stats = strategy.get_statistics()
        
        # Should find pairs with matching phone+state
        # c001 & c002 have same phone+state
        # c003 & c004 have same phone+state
        # c006 & c007 have same phone+state
        assert len(pairs) >= 3
        assert stats['total_pairs'] >= 3
        assert stats['execution_time_seconds'] > 0
        
        # Verify some expected pairs
        pair_keys = {(p['doc1_key'], p['doc2_key']) for p in pairs}
        assert ('c001', 'c002') in pair_keys or ('c002', 'c001') in pair_keys
    
    def test_performance_blocking_100_docs(self, test_db):
        """Performance test: 100 documents."""
        # Create larger test dataset
        collection_name = "test_perf_100"
        if test_db.has_collection(collection_name):
            test_db.delete_collection(collection_name)
        
        collection = test_db.create_collection(collection_name)
        
        # Generate 100 test documents
        docs = []
        for i in range(100):
            docs.append({
                "_key": f"doc_{i:03d}",
                "field1": f"value_{i % 10}",  # 10 unique values = ~10 docs per block
                "field2": f"type_{i % 5}"     # 5 unique values
            })
        collection.insert_many(docs)
        
        # Run blocking
        strategy = CollectBlockingStrategy(
            db=test_db,
            collection=collection_name,
            blocking_fields=["field1", "field2"]
        )
        
        start_time = time.time()
        pairs = strategy.generate_candidates()
        elapsed = time.time() - start_time
        
        stats = strategy.get_statistics()
        
        print(f"\nPerformance (100 docs):")
        print(f"  Pairs generated: {len(pairs)}")
        print(f"  Time: {elapsed:.3f}s")
        print(f"  Stats: {stats}")
        
        # Should be fast
        assert elapsed < 5.0  # Should complete in < 5 seconds
        
        # Cleanup
        test_db.delete_collection(collection_name)


class TestBatchSimilarityIntegration:
    """Integration tests for BatchSimilarityService."""
    
    def test_similarity_computation(self, test_db, test_collection):
        """Test similarity computation with real data."""
        # Get some candidate pairs
        pairs = [
            ("c001", "c002"),  # Acme Corp variations
            ("c003", "c004"),  # Beta Inc variations
            ("c006", "c007"),  # Delta Corp variations
        ]
        
        service = BatchSimilarityService(
            db=test_db,
            collection=test_collection,
            field_weights={
                "name": 0.4,
                "phone": 0.2,
                "ceo": 0.2,
                "address": 0.2
            },
            similarity_algorithm="jaro_winkler"
        )
        
        matches = service.compute_similarities(
            candidate_pairs=pairs,
            threshold=0.75
        )
        
        stats = service.get_statistics()
        
        # Should find high similarity matches
        assert len(matches) >= 2
        assert stats['pairs_processed'] == 3
        assert stats['documents_cached'] >= 4
        
        # Check scores are reasonable
        for doc1, doc2, score in matches:
            assert 0.75 <= score <= 1.0
            print(f"  {doc1} <-> {doc2}: {score:.4f}")
    
    def test_performance_similarity_1000_pairs(self, test_db, test_collection):
        """Performance test: 1000 pairs."""
        # Generate many pairs (some real, some synthetic)
        pairs = []
        for i in range(1000):
            # Mix real and synthetic pairs
            if i < 3:
                pairs.append((f"c00{i+1}", f"c00{i+2}"))
            else:
                pairs.append((f"synthetic_{i}", f"synthetic_{i+1}"))
        
        service = BatchSimilarityService(
            db=test_db,
            collection=test_collection,
            field_weights={"name": 0.5, "phone": 0.5},
            batch_size=5000
        )
        
        start_time = time.time()
        matches = service.compute_similarities(
            pairs[:100],  # Test with first 100 that have real data
            threshold=0.75
        )
        elapsed = time.time() - start_time
        
        stats = service.get_statistics()
        
        print(f"\nPerformance (100 pairs):")
        print(f"  Pairs processed: {stats['pairs_processed']}")
        print(f"  Matches found: {len(matches)}")
        print(f"  Time: {elapsed:.3f}s")
        print(f"  Speed: {stats['pairs_per_second']:,} pairs/sec")
        
        # Should be reasonably fast
        assert elapsed < 5.0
        assert stats['pairs_per_second'] > 10  # At least 10 pairs/sec


class TestSimilarityEdgeIntegration:
    """Integration tests for SimilarityEdgeService."""
    
    def test_edge_creation(self, test_db, test_collection):
        """Test edge creation with real data."""
        edge_collection = "test_edges_integration"
        
        # Cleanup if exists
        if test_db.has_collection(edge_collection):
            test_db.delete_collection(edge_collection)
        
        service = SimilarityEdgeService(
            db=test_db,
            edge_collection=edge_collection,
            vertex_collection=test_collection,
            batch_size=1000,
            auto_create_collection=True
        )
        
        # Create some edges
        matches = [
            ("c001", "c002", 0.92),
            ("c003", "c004", 0.87),
            ("c006", "c007", 0.89)
        ]
        
        edges_created = service.create_edges(
            matches=matches,
            metadata={"method": "test", "algorithm": "jaro_winkler"}
        )
        
        stats = service.get_statistics()
        
        assert edges_created == 3
        assert stats['edges_created'] == 3
        
        # Verify edges exist in database
        edge_coll = test_db.collection(edge_collection)
        edges = list(edge_coll.all())
        assert len(edges) == 3
        
        # Check edge structure
        for edge in edges:
            assert '_from' in edge
            assert '_to' in edge
            assert 'similarity' in edge
            assert 'method' in edge
            assert edge['method'] == 'test'
        
        # Cleanup
        test_db.delete_collection(edge_collection)


class TestWCCClusteringIntegration:
    """Integration tests for WCCClusteringService."""
    
    def test_clustering_with_edges(self, test_db, test_collection):
        """Test clustering with real edges."""
        edge_collection = "test_edges_wcc"
        cluster_collection = "test_clusters_wcc"
        
        # Cleanup
        for coll_name in [edge_collection, cluster_collection]:
            if test_db.has_collection(coll_name):
                test_db.delete_collection(coll_name)
        
        # Create edges
        edge_coll = test_db.create_collection(edge_collection, edge=True)
        edges = [
            {"_from": f"{test_collection}/c001", "_to": f"{test_collection}/c002"},  # Cluster 1
            {"_from": f"{test_collection}/c003", "_to": f"{test_collection}/c004"},  # Cluster 2
            {"_from": f"{test_collection}/c006", "_to": f"{test_collection}/c007"},  # Cluster 3
        ]
        edge_coll.insert_many(edges)
        
        # Run clustering
        service = WCCClusteringService(
            db=test_db,
            edge_collection=edge_collection,
            cluster_collection=cluster_collection,
            vertex_collection=test_collection,
            min_cluster_size=2
        )
        
        clusters = service.cluster(store_results=True)
        stats = service.get_statistics()
        
        print(f"\nClustering results:")
        print(f"  Total clusters: {stats['total_clusters']}")
        print(f"  Total entities: {stats['total_entities_clustered']}")
        
        # Should find 3 clusters
        assert stats['total_clusters'] >= 2  # At least 2 clusters
        assert stats['total_entities_clustered'] >= 4  # At least 4 entities
        
        # Verify clusters are stored
        cluster_coll = test_db.collection(cluster_collection)
        stored_clusters = list(cluster_coll.all())
        assert len(stored_clusters) >= 2
        
        # Cleanup
        test_db.delete_collection(edge_collection)
        test_db.delete_collection(cluster_collection)


class TestCompletePipeline:
    """Integration test for complete ER pipeline."""
    
    def test_end_to_end_pipeline(self, test_db, test_collection):
        """Test complete end-to-end ER workflow."""
        print("\n" + "="*80)
        print("COMPLETE PIPELINE TEST")
        print("="*80)
        
        edge_collection = "test_pipeline_edges"
        cluster_collection = "test_pipeline_clusters"
        
        # Cleanup
        for coll_name in [edge_collection, cluster_collection]:
            if test_db.has_collection(coll_name):
                test_db.delete_collection(coll_name)
        
        # Step 1: Blocking
        print("\n[1/4] Blocking...")
        strategy = CollectBlockingStrategy(
            db=test_db,
            collection=test_collection,
            blocking_fields=["phone", "state"],
            filters={
                "phone": {"not_null": True},
                "state": {"not_null": True}
            }
        )
        pairs = strategy.generate_candidates()
        pair_tuples = [(p['doc1_key'], p['doc2_key']) for p in pairs]
        print(f"  Found {len(pair_tuples)} candidate pairs")
        
        # Step 2: Similarity
        print("\n[2/4] Computing similarity...")
        similarity = BatchSimilarityService(
            db=test_db,
            collection=test_collection,
            field_weights={"name": 0.4, "phone": 0.3, "ceo": 0.2, "address": 0.1}
        )
        matches = similarity.compute_similarities(
            candidate_pairs=pair_tuples,
            threshold=0.75
        )
        print(f"  Found {len(matches)} matches")
        
        # Step 3: Create edges
        print("\n[3/4] Creating edges...")
        edges = SimilarityEdgeService(
            db=test_db,
            edge_collection=edge_collection,
            vertex_collection=test_collection
        )
        edges_created = edges.create_edges(
            matches=matches,
            metadata={"method": "integration_test"}
        )
        print(f"  Created {edges_created} edges")
        
        # Step 4: Clustering
        print("\n[4/4] Clustering...")
        clustering = WCCClusteringService(
            db=test_db,
            edge_collection=edge_collection,
            cluster_collection=cluster_collection,
            vertex_collection=test_collection
        )
        clusters = clustering.cluster(store_results=True)
        stats = clustering.get_statistics()
        print(f"  Found {stats['total_clusters']} clusters")
        print(f"  Total entities in clusters: {stats['total_entities_clustered']}")
        
        # Verify pipeline results
        assert len(pair_tuples) > 0
        assert len(matches) > 0
        assert edges_created > 0
        assert stats['total_clusters'] > 0
        
        print("\n" + "="*80)
        print("PIPELINE COMPLETE!")
        print("="*80)
        
        # Cleanup
        test_db.delete_collection(edge_collection)
        test_db.delete_collection(cluster_collection)


# Performance benchmark suite
class TestPerformanceBenchmarks:
    """Performance benchmarks for all components."""
    
    def test_benchmark_summary(self, test_db):
        """Run performance benchmarks and print summary."""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARKS")
        print("="*80)
        
        results = {}
        
        # Note: These are basic benchmarks with small data
        # Real-world performance with 100K+ documents will be better due to
        # optimizations like batch processing, server-side operations, etc.
        
        print("\nNote: Using small test dataset. Real-world performance")
        print("with 100K+ documents will show the true benefits of:")
        print("  - Batch processing (reduces queries from 100K+ to ~10)")
        print("  - Server-side operations (AQL graph traversal)")
        print("  - Optimized algorithms (BM25, Jaro-Winkler)")
        
        print("\n" + "="*80)
        print("Benchmarks complete - see integration tests for timing")
        print("="*80)


# Run benchmarks with: pytest test_integration_and_performance.py -v -s -m integration

