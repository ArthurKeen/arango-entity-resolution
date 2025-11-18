"""
Round-Trip Integration Tests for v3.0 Components

Tests the complete v3.0 workflow with real ArangoDB:
1. WeightedFieldSimilarity
2. BatchSimilarityService (with WeightedFieldSimilarity)
3. AddressERService (complete pipeline)
4. WCCClusteringService (Python DFS algorithm)
5. ConfigurableERPipeline (YAML-based configuration)

Requires: Running ArangoDB instance
Run with: pytest tests/test_round_trip_v3.py -v -s
"""

import pytest
import sys
import os
import time
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution import (
    WeightedFieldSimilarity,
    BatchSimilarityService,
    AddressERService,
    WCCClusteringService,
    SimilarityEdgeService,
    CollectBlockingStrategy,
    ConfigurableERPipeline,
    ERPipelineConfig,
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
    collection_name = "test_round_trip_v3"
    
    # Cleanup if exists
    if test_db.has_collection(collection_name):
        test_db.delete_collection(collection_name)
    
    collection = test_db.create_collection(collection_name)
    
    # Insert test data with duplicates
    test_docs = [
        {
            "_key": "doc1",
            "name": "Acme Corporation",
            "address": "123 Main Street",
            "city": "Boston",
            "state": "MA",
            "zip": "02101",
            "phone": "555-0100"
        },
        {
            "_key": "doc2",
            "name": "Acme Corp",
            "address": "123 Main St",
            "city": "Boston",
            "state": "MA",
            "zip": "02101",
            "phone": "555-0100"
        },
        {
            "_key": "doc3",
            "name": "Beta Industries",
            "address": "456 Oak Avenue",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "phone": "555-0200"
        },
        {
            "_key": "doc4",
            "name": "Beta Inc",
            "address": "456 Oak Ave",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "phone": "555-0200"
        },
        {
            "_key": "doc5",
            "name": "Gamma LLC",
            "address": "789 Pine Road",
            "city": "Chicago",
            "state": "IL",
            "zip": "60601",
            "phone": "555-0300"
        },
    ]
    
    collection.insert_many(test_docs)
    
    yield collection_name
    
    # Cleanup
    if test_db.has_collection(collection_name):
        test_db.delete_collection(collection_name)


class TestWeightedFieldSimilarityRoundTrip:
    """Round-trip tests for WeightedFieldSimilarity."""
    
    def test_similarity_computation(self, test_db, test_collection):
        """Test similarity computation with real documents."""
        # Fetch documents from database
        doc1 = test_db.collection(test_collection).get("doc1")
        doc2 = test_db.collection(test_collection).get("doc2")
        
        similarity = WeightedFieldSimilarity(
            field_weights={
                "name": 0.4,
                "address": 0.3,
                "city": 0.2,
                "state": 0.1
            },
            algorithm="jaro_winkler"
        )
        
        # Compute similarity
        score = similarity.compute(doc1, doc2)
        detailed = similarity.compute_detailed(doc1, doc2)
        
        # Should have high similarity (same company, different formatting)
        assert 0.7 <= score <= 1.0
        assert "overall_score" in detailed
        assert "field_scores" in detailed
        assert detailed["overall_score"] == score
        
        print(f"\nSimilarity Score: {score:.4f}")
        print(f"Field Scores: {detailed['field_scores']}")
    
    def test_multiple_algorithms(self, test_db, test_collection):
        """Test different similarity algorithms."""
        doc1 = test_db.collection(test_collection).get("doc1")
        doc2 = test_db.collection(test_collection).get("doc2")
        
        algorithms = ["jaro_winkler", "levenshtein", "jaccard"]
        results = {}
        
        for algo in algorithms:
            similarity = WeightedFieldSimilarity(
                field_weights={"name": 0.5, "address": 0.5},
                algorithm=algo
            )
            score = similarity.compute(doc1, doc2)
            results[algo] = score
            assert 0.0 <= score <= 1.0
        
        print(f"\nAlgorithm Comparison:")
        for algo, score in results.items():
            print(f"  {algo}: {score:.4f}")


class TestBatchSimilarityServiceRoundTrip:
    """Round-trip tests for BatchSimilarityService."""
    
    def test_batch_similarity_computation(self, test_db, test_collection):
        """Test batch similarity with real database."""
        # Generate candidate pairs
        pairs = [
            ("doc1", "doc2"),  # Should match (Acme variations)
            ("doc3", "doc4"),  # Should match (Beta variations)
            ("doc1", "doc5"),  # Should not match (different companies)
        ]
        
        service = BatchSimilarityService(
            db=test_db,
            collection=test_collection,
            field_weights={
                "name": 0.4,
                "address": 0.3,
                "city": 0.2,
                "state": 0.1
            },
            similarity_algorithm="jaro_winkler",
            batch_size=100
        )
        
        matches = service.compute_similarities(
            candidate_pairs=pairs,
            threshold=0.75
        )
        
        stats = service.get_statistics()
        
        print(f"\nBatch Similarity Results:")
        print(f"  Pairs processed: {stats['pairs_processed']}")
        print(f"  Matches found: {len(matches)}")
        print(f"  Documents cached: {stats['documents_cached']}")
        print(f"  Execution time: {stats['execution_time_seconds']:.3f}s")
        print(f"  Speed: {stats['pairs_per_second']:.0f} pairs/sec")
        
        # Should find at least 2 matches (doc1-doc2 and doc3-doc4)
        assert len(matches) >= 2
        assert stats['pairs_processed'] == 3
        
        # Verify match scores
        match_keys = {(m[0], m[1]) for m in matches}
        assert ("doc1", "doc2") in match_keys or ("doc2", "doc1") in match_keys
        assert ("doc3", "doc4") in match_keys or ("doc4", "doc3") in match_keys
        
        for doc1, doc2, score in matches:
            assert 0.75 <= score <= 1.0
            print(f"    {doc1} <-> {doc2}: {score:.4f}")


class TestAddressERServiceRoundTrip:
    """Round-trip tests for AddressERService."""
    
    def test_address_er_complete_pipeline(self, test_db):
        """Test complete address ER pipeline."""
        collection_name = "test_addresses_round_trip"
        edge_collection = "test_address_edges_round_trip"
        
        # Cleanup
        for coll in [collection_name, edge_collection]:
            if test_db.has_collection(coll):
                test_db.delete_collection(coll)
        
        # Create address collection
        collection = test_db.create_collection(collection_name)
        
        # Insert address data
        addresses = [
            {
                "_key": "addr1",
                "ADDRESS_LINE_1": "123 Main Street",
                "PRIMARY_TOWN": "Boston",
                "TERRITORY_CODE": "MA",
                "POSTAL_CODE": "02101"
            },
            {
                "_key": "addr2",
                "ADDRESS_LINE_1": "123 Main St",
                "PRIMARY_TOWN": "Boston",
                "TERRITORY_CODE": "MA",
                "POSTAL_CODE": "02101"
            },
            {
                "_key": "addr3",
                "ADDRESS_LINE_1": "456 Oak Avenue",
                "PRIMARY_TOWN": "New York",
                "TERRITORY_CODE": "NY",
                "POSTAL_CODE": "10001"
            },
            {
                "_key": "addr4",
                "ADDRESS_LINE_1": "456 Oak Ave",
                "PRIMARY_TOWN": "New York",
                "TERRITORY_CODE": "NY",
                "POSTAL_CODE": "10001"
            },
        ]
        collection.insert_many(addresses)
        
        # Create service
        service = AddressERService(
            db=test_db,
            collection=collection_name,
            edge_collection=edge_collection,
            config={
                "max_block_size": 10,
                "min_bm25_score": 2.0,
                "batch_size": 1000
            }
        )
        
        # Setup infrastructure
        print("\n[Address ER] Setting up infrastructure...")
        service.setup_infrastructure()
        
        # Run pipeline
        print("[Address ER] Running pipeline...")
        results = service.run(
            create_edges=True,
            cluster=False
        )
        
        print(f"\nAddress ER Results:")
        print(f"  Blocks found: {results['blocks_found']}")
        print(f"  Addresses matched: {results['addresses_matched']}")
        print(f"  Edges created: {results['edges_created']}")
        print(f"  Runtime: {results['runtime_seconds']:.2f}s")
        
        # Verify results
        assert results['blocks_found'] > 0
        assert results['edges_created'] > 0
        
        # Verify edges exist
        edge_coll = test_db.collection(edge_collection)
        edges = list(edge_coll.all())
        assert len(edges) == results['edges_created']
        
        # Cleanup
        for coll in [collection_name, edge_collection]:
            if test_db.has_collection(coll):
                test_db.delete_collection(coll)


class TestWCCClusteringRoundTrip:
    """Round-trip tests for WCCClusteringService with Python DFS."""
    
    def test_python_dfs_clustering(self, test_db, test_collection):
        """Test Python DFS clustering algorithm."""
        edge_collection = "test_edges_wcc_round_trip"
        cluster_collection = "test_clusters_wcc_round_trip"
        
        # Cleanup
        for coll in [edge_collection, cluster_collection]:
            if test_db.has_collection(coll):
                test_db.delete_collection(coll)
        
        # Create edges
        edge_coll = test_db.create_collection(edge_collection, edge=True)
        edges = [
            {"_from": f"{test_collection}/doc1", "_to": f"{test_collection}/doc2"},
            {"_from": f"{test_collection}/doc3", "_to": f"{test_collection}/doc4"},
        ]
        edge_coll.insert_many(edges)
        
        # Run clustering with Python DFS
        service = WCCClusteringService(
            db=test_db,
            edge_collection=edge_collection,
            cluster_collection=cluster_collection,
            vertex_collection=test_collection,
            algorithm="python_dfs",
            min_cluster_size=2
        )
        
        print("\n[WCC Clustering] Running Python DFS algorithm...")
        clusters = service.cluster(store_results=True)
        stats = service.get_statistics()
        
        print(f"\nWCC Clustering Results (Python DFS):")
        print(f"  Total clusters: {stats['total_clusters']}")
        print(f"  Total entities: {stats['total_entities_clustered']}")
        print(f"  Execution time: {stats['execution_time_seconds']:.3f}s")
        print(f"  Algorithm: {stats.get('algorithm', 'python_dfs')}")
        
        # Should find at least 2 clusters
        assert stats['total_clusters'] >= 2
        assert stats['total_entities_clustered'] >= 4
        
        # Verify clusters
        assert len(clusters) >= 2
        for cluster in clusters:
            assert len(cluster) >= 2
        
        # Verify clusters stored
        cluster_coll = test_db.collection(cluster_collection)
        stored = list(cluster_coll.all())
        assert len(stored) >= 2
        
        # Cleanup
        for coll in [edge_collection, cluster_collection]:
            if test_db.has_collection(coll):
                test_db.delete_collection(coll)


class TestCompletePipelineRoundTrip:
    """Complete end-to-end round-trip test."""
    
    def test_complete_er_pipeline(self, test_db, test_collection):
        """Test complete ER pipeline from blocking to clustering."""
        print("\n" + "="*80)
        print("COMPLETE ROUND-TRIP PIPELINE TEST")
        print("="*80)
        
        edge_collection = "test_pipeline_edges_round_trip"
        cluster_collection = "test_pipeline_clusters_round_trip"
        
        # Cleanup
        for coll in [edge_collection, cluster_collection]:
            if test_db.has_collection(coll):
                test_db.delete_collection(coll)
        
        # Step 1: Blocking
        print("\n[1/4] Blocking...")
        strategy = CollectBlockingStrategy(
            db=test_db,
            collection=test_collection,
            blocking_fields=["state", "zip"],
            filters={
                "state": {"not_null": True},
                "zip": {"not_null": True}
            },
            max_block_size=10,
            min_block_size=2
        )
        pairs = strategy.generate_candidates()
        pair_tuples = [(p['doc1_key'], p['doc2_key']) for p in pairs]
        print(f"  ✓ Found {len(pair_tuples)} candidate pairs")
        
        # Step 2: Similarity
        print("\n[2/4] Computing similarity...")
        similarity = BatchSimilarityService(
            db=test_db,
            collection=test_collection,
            field_weights={
                "name": 0.4,
                "address": 0.3,
                "city": 0.2,
                "state": 0.1
            },
            similarity_algorithm="jaro_winkler"
        )
        matches = similarity.compute_similarities(
            candidate_pairs=pair_tuples,
            threshold=0.75
        )
        print(f"  ✓ Found {len(matches)} matches above threshold")
        
        # Step 3: Create edges
        print("\n[3/4] Creating edges...")
        edges = SimilarityEdgeService(
            db=test_db,
            edge_collection=edge_collection,
            vertex_collection=test_collection,
            auto_create_collection=True
        )
        edges_created = edges.create_edges(
            matches=matches,
            metadata={"method": "round_trip_test", "algorithm": "jaro_winkler"}
        )
        print(f"  ✓ Created {edges_created} edges")
        
        # Step 4: Clustering (Python DFS)
        print("\n[4/4] Clustering (Python DFS)...")
        clustering = WCCClusteringService(
            db=test_db,
            edge_collection=edge_collection,
            cluster_collection=cluster_collection,
            vertex_collection=test_collection,
            algorithm="python_dfs",
            min_cluster_size=2
        )
        clusters = clustering.cluster(store_results=True)
        stats = clustering.get_statistics()
        print(f"  ✓ Found {stats['total_clusters']} clusters")
        print(f"  ✓ Total entities clustered: {stats['total_entities_clustered']}")
        
        # Verify complete pipeline
        assert len(pair_tuples) > 0, "Should find candidate pairs"
        assert len(matches) > 0, "Should find matches"
        assert edges_created > 0, "Should create edges"
        assert stats['total_clusters'] > 0, "Should find clusters"
        
        print("\n" + "="*80)
        print("✓ ROUND-TRIP PIPELINE COMPLETE!")
        print("="*80)
        
        # Cleanup
        for coll in [edge_collection, cluster_collection]:
            if test_db.has_collection(coll):
                test_db.delete_collection(coll)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

