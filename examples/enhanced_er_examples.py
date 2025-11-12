"""
Enhanced Entity Resolution Examples

This file demonstrates how to use the new v2.0 features:
- CollectBlockingStrategy
- BM25BlockingStrategy
- BatchSimilarityService  
- SimilarityEdgeService
- WCCClusteringService

These examples show generic, reusable patterns that work with any schema.
"""

from entity_resolution import (
    CollectBlockingStrategy,
    BM25BlockingStrategy,
    BatchSimilarityService,
    SimilarityEdgeService,
    WCCClusteringService,
    get_database
)


def example_1_collect_blocking():
    """
    Example 1: Composite Key Blocking with COLLECT
    
    Use case: Block entities by exact match on multiple fields
    (e.g., phone + state, email + country, etc.)
    """
    print("=" * 80)
    print("Example 1: COLLECT-based Composite Key Blocking")
    print("=" * 80)
    
    db = get_database()
    
    # Create blocking strategy for phone + state
    strategy = CollectBlockingStrategy(
        db=db,
        collection="companies",  # Your collection name
        blocking_fields=["phone", "state"],  # Your blocking fields
        filters={
            "phone": {
                "not_null": True,
                "min_length": 10,
                "not_equal": ["0000000000", "UNKNOWN"]
            },
            "state": {
                "not_null": True
            }
        },
        max_block_size=100,  # Skip blocks larger than this
        min_block_size=2     # Skip singletons
    )
    
    # Generate candidate pairs
    print("\nGenerating candidate pairs...")
    pairs = strategy.generate_candidates()
    
    # Get statistics
    stats = strategy.get_statistics()
    print(f"\nResults:")
    print(f"  Candidate pairs generated: {stats['total_pairs']:,}")
    print(f"  Execution time: {stats['execution_time_seconds']}s")
    print(f"  Blocking fields: {', '.join(stats['blocking_fields'])}")
    
    # Show sample pairs
    print(f"\nSample pairs (first 3):")
    for i, pair in enumerate(pairs[:3]):
        print(f"  {i+1}. {pair['doc1_key']} <-> {pair['doc2_key']}")
        print(f"     Blocking keys: {pair['blocking_keys']}")
        print(f"     Block size: {pair['block_size']}")
    
    return pairs


def example_2_bm25_blocking():
    """
    Example 2: BM25 Fuzzy Text Blocking
    
    Use case: Find similar entities based on fuzzy text matching
    (e.g., similar company names, person names, etc.)
    
    Prerequisites:
    - ArangoSearch view must be created first (one-time setup)
    """
    print("\n" + "=" * 80)
    print("Example 2: BM25 Fuzzy Text Blocking")
    print("=" * 80)
    
    db = get_database()
    
    # First, create search view (one-time setup)
    # Uncomment and adjust for your schema:
    """
    if not db.has_view('companies_search'):
        db.create_view(
            name='companies_search',
            view_type='arangosearch',
            properties={
                'links': {
                    'companies': {
                        'fields': {
                            'company_name': {'analyzers': ['text_en']}
                        }
                    }
                }
            }
        )
    """
    
    # Create BM25 blocking strategy
    strategy = BM25BlockingStrategy(
        db=db,
        collection="companies",  # Your collection
        search_view="companies_search",  # Your search view
        search_field="company_name",  # Field to search on
        bm25_threshold=2.0,  # Minimum BM25 score
        limit_per_entity=20,  # Max candidates per entity
        blocking_field="state",  # Optional: constrain by state
        filters={
            "company_name": {
                "not_null": True,
                "min_length": 3
            },
            "state": {
                "not_null": True
            }
        }
    )
    
    # Generate candidate pairs
    print("\nGenerating candidate pairs with BM25...")
    pairs = strategy.generate_candidates()
    
    # Get statistics
    stats = strategy.get_statistics()
    print(f"\nResults:")
    print(f"  Candidate pairs generated: {stats['total_pairs']:,}")
    print(f"  Average BM25 score: {stats['avg_bm25_score']}")
    print(f"  Max BM25 score: {stats['max_bm25_score']}")
    print(f"  Execution time: {stats['execution_time_seconds']}s")
    
    # Show sample pairs with BM25 scores
    print(f"\nSample pairs with BM25 scores (first 3):")
    for i, pair in enumerate(pairs[:3]):
        print(f"  {i+1}. {pair['doc1_key']} <-> {pair['doc2_key']}")
        print(f"     BM25 score: {pair['bm25_score']:.2f}")
        if 'blocking_field_value' in pair:
            print(f"     State: {pair['blocking_field_value']}")
    
    return pairs


def example_3_batch_similarity():
    """
    Example 3: Batch Similarity Computation
    
    Use case: Compute similarity scores for candidate pairs efficiently
    Supports multiple algorithms: Jaro-Winkler, Levenshtein, Jaccard
    """
    print("\n" + "=" * 80)
    print("Example 3: Batch Similarity Computation")
    print("=" * 80)
    
    db = get_database()
    
    # First, get candidate pairs (from blocking)
    # For demo, we'll assume we have pairs from previous example
    candidate_pairs = [
        ("company_001", "company_002"),
        ("company_003", "company_004"),
        ("company_005", "company_006")
    ]
    
    # Create similarity service
    service = BatchSimilarityService(
        db=db,
        collection="companies",
        field_weights={
            "company_name": 0.4,
            "ceo_name": 0.3,
            "address": 0.2,
            "city": 0.1
        },
        similarity_algorithm="jaro_winkler",  # or "levenshtein", "jaccard", or custom
        batch_size=5000,
        normalization_config={
            "strip": True,
            "case": "upper",
            "remove_extra_whitespace": True
        }
    )
    
    # Compute similarities
    print("\nComputing similarities...")
    matches = service.compute_similarities(
        candidate_pairs=candidate_pairs,
        threshold=0.75,
        return_all=False  # Only return matches above threshold
    )
    
    # Get statistics
    stats = service.get_statistics()
    print(f"\nResults:")
    print(f"  Pairs processed: {stats['pairs_processed']:,}")
    print(f"  Matches above threshold: {stats['pairs_above_threshold']:,}")
    print(f"  Documents cached: {stats['documents_cached']:,}")
    print(f"  Execution time: {stats['execution_time_seconds']}s")
    print(f"  Performance: {stats['pairs_per_second']:,} pairs/second")
    
    # Show matches
    print(f"\nMatches (score >= 0.75):")
    for doc1_key, doc2_key, score in matches:
        print(f"  {doc1_key} <-> {doc2_key}: {score:.4f}")
    
    return matches


def example_4_detailed_similarity():
    """
    Example 4: Detailed Similarity with Per-Field Scores
    
    Use case: Need to see individual field contributions to similarity
    """
    print("\n" + "=" * 80)
    print("Example 4: Detailed Similarity Computation")
    print("=" * 80)
    
    db = get_database()
    
    candidate_pairs = [
        ("company_001", "company_002"),
    ]
    
    service = BatchSimilarityService(
        db=db,
        collection="companies",
        field_weights={
            "company_name": 0.4,
            "ceo_name": 0.3,
            "address": 0.2,
            "city": 0.1
        }
    )
    
    # Get detailed similarity results
    print("\nComputing detailed similarities...")
    detailed_matches = service.compute_similarities_detailed(
        candidate_pairs=candidate_pairs,
        threshold=0.75
    )
    
    # Show detailed results
    print(f"\nDetailed matches:")
    for match in detailed_matches:
        print(f"\n  Pair: {match['doc1_key']} <-> {match['doc2_key']}")
        print(f"  Overall score: {match['overall_score']:.4f}")
        print(f"  Field scores:")
        for field, score in match['field_scores'].items():
            print(f"    {field}: {score:.4f}")
    
    return detailed_matches


def example_5_create_edges():
    """
    Example 5: Create Similarity Edges in Bulk
    
    Use case: Store similarity results as graph edges for clustering
    """
    print("\n" + "=" * 80)
    print("Example 5: Bulk Edge Creation")
    print("=" * 80)
    
    db = get_database()
    
    # Matches from similarity computation
    matches = [
        ("company_001", "company_002", 0.92),
        ("company_003", "company_004", 0.87),
        ("company_005", "company_006", 0.85)
    ]
    
    # Create edge service
    service = SimilarityEdgeService(
        db=db,
        edge_collection="similarTo",  # Your edge collection
        vertex_collection="companies",  # Your vertex collection
        batch_size=1000
    )
    
    # Create edges with metadata
    print("\nCreating similarity edges...")
    edges_created = service.create_edges(
        matches=matches,
        metadata={
            "method": "phone_blocking",
            "algorithm": "jaro_winkler",
            "threshold": 0.75,
            "run_id": "run_20251112"
        },
        bidirectional=False  # Set True for undirected graph
    )
    
    # Get statistics
    stats = service.get_statistics()
    print(f"\nResults:")
    print(f"  Edges created: {stats['edges_created']:,}")
    print(f"  Batches processed: {stats['batches_processed']}")
    print(f"  Execution time: {stats['execution_time_seconds']}s")
    print(f"  Performance: {stats['edges_per_second']:,} edges/second")
    
    return edges_created


def example_6_wcc_clustering():
    """
    Example 6: Weakly Connected Components Clustering
    
    Use case: Find groups of similar entities (clusters)
    """
    print("\n" + "=" * 80)
    print("Example 6: WCC Clustering")
    print("=" * 80)
    
    db = get_database()
    
    # Create clustering service
    service = WCCClusteringService(
        db=db,
        edge_collection="similarTo",
        cluster_collection="entity_clusters",
        vertex_collection="companies",
        min_cluster_size=2
    )
    
    # Run clustering
    print("\nRunning WCC clustering...")
    clusters = service.cluster(
        store_results=True,
        truncate_existing=True
    )
    
    # Get statistics
    stats = service.get_statistics()
    print(f"\nResults:")
    print(f"  Total clusters: {stats['total_clusters']:,}")
    print(f"  Total entities clustered: {stats['total_entities_clustered']:,}")
    print(f"  Average cluster size: {stats['avg_cluster_size']:.1f}")
    print(f"  Largest cluster: {stats['max_cluster_size']}")
    print(f"  Execution time: {stats['execution_time_seconds']}s")
    
    # Show size distribution
    print(f"\n  Cluster size distribution:")
    for size_range, count in stats['cluster_size_distribution'].items():
        print(f"    Size {size_range}: {count} clusters")
    
    # Show sample clusters
    print(f"\nSample clusters (first 3):")
    for i, cluster in enumerate(clusters[:3]):
        print(f"  Cluster {i+1}: {len(cluster)} entities")
        print(f"    Members: {cluster[:5]}...")  # Show first 5
    
    return clusters


def example_7_validate_clusters():
    """
    Example 7: Validate Cluster Quality
    
    Use case: Ensure clusters are valid and consistent
    """
    print("\n" + "=" * 80)
    print("Example 7: Cluster Validation")
    print("=" * 80)
    
    db = get_database()
    
    service = WCCClusteringService(
        db=db,
        edge_collection="similarTo",
        cluster_collection="entity_clusters"
    )
    
    # Validate clusters
    print("\nValidating clusters...")
    validation = service.validate_clusters()
    
    print(f"\nValidation results:")
    print(f"  Valid: {validation['valid']}")
    print(f"  Entities checked: {validation['entities_checked']:,}")
    print(f"  Edges checked: {validation['edges_checked']:,}")
    print(f"  Checks performed: {', '.join(validation['checks_performed'])}")
    
    if validation['issues']:
        print(f"\n  Issues found: {len(validation['issues'])}")
        for issue in validation['issues'][:5]:  # Show first 5
            print(f"    - {issue['type']}: {issue}")
    else:
        print(f"\n  ✅ No issues found - clusters are valid!")
    
    return validation


def example_8_complete_pipeline():
    """
    Example 8: Complete Entity Resolution Pipeline
    
    Use case: Full end-to-end ER workflow
    """
    print("\n" + "=" * 80)
    print("Example 8: Complete ER Pipeline")
    print("=" * 80)
    
    db = get_database()
    
    # Step 1: Blocking (multiple strategies)
    print("\n[1/5] Blocking - Generating candidate pairs...")
    
    phone_strategy = CollectBlockingStrategy(
        db=db,
        collection="companies",
        blocking_fields=["phone", "state"],
        filters={
            "phone": {"not_null": True, "min_length": 10},
            "state": {"not_null": True}
        }
    )
    phone_pairs = phone_strategy.generate_candidates()
    print(f"  Phone blocking: {len(phone_pairs):,} pairs")
    
    # Could add more strategies here (BM25, etc.)
    # Combine and deduplicate
    all_pairs = set()
    for pair in phone_pairs:
        all_pairs.add((pair['doc1_key'], pair['doc2_key']))
    
    print(f"  Total unique pairs: {len(all_pairs):,}")
    
    # Step 2: Similarity computation
    print("\n[2/5] Similarity - Computing scores...")
    
    similarity = BatchSimilarityService(
        db=db,
        collection="companies",
        field_weights={
            "company_name": 0.4,
            "ceo_name": 0.3,
            "address": 0.2,
            "city": 0.1
        },
        similarity_algorithm="jaro_winkler"
    )
    matches = similarity.compute_similarities(
        candidate_pairs=list(all_pairs),
        threshold=0.75
    )
    print(f"  Matches found: {len(matches):,}")
    
    # Step 3: Create edges
    print("\n[3/5] Edges - Creating similarity graph...")
    
    edges = SimilarityEdgeService(
        db=db,
        edge_collection="similarTo",
        vertex_collection="companies"
    )
    edges_created = edges.create_edges(
        matches=matches,
        metadata={
            "method": "hybrid_blocking",
            "algorithm": "jaro_winkler",
            "threshold": 0.75
        }
    )
    print(f"  Edges created: {edges_created:,}")
    
    # Step 4: Clustering
    print("\n[4/5] Clustering - Finding connected components...")
    
    clustering = WCCClusteringService(
        db=db,
        edge_collection="similarTo",
        cluster_collection="entity_clusters",
        vertex_collection="companies"
    )
    clusters = clustering.cluster(store_results=True)
    print(f"  Clusters found: {len(clusters):,}")
    
    # Step 5: Validation
    print("\n[5/5] Validation - Checking cluster quality...")
    
    validation = clustering.validate_clusters()
    print(f"  Validation: {'✅ PASSED' if validation['valid'] else '❌ FAILED'}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("Pipeline Complete!")
    print("=" * 80)
    print(f"  Candidate pairs: {len(all_pairs):,}")
    print(f"  Matches: {len(matches):,}")
    print(f"  Edges: {edges_created:,}")
    print(f"  Clusters: {len(clusters):,}")
    
    return {
        'pairs': len(all_pairs),
        'matches': len(matches),
        'edges': edges_created,
        'clusters': len(clusters)
    }


def main():
    """
    Run all examples (or comment out ones you don't want to run)
    """
    print("\n")
    print("=" * 80)
    print("Enhanced Entity Resolution Examples (v2.0)")
    print("=" * 80)
    print("\nThese examples demonstrate generic patterns that work with any schema.")
    print("Adjust collection names, field names, and filters for your data.\n")
    
    # Run examples
    # Uncomment the ones you want to try:
    
    # example_1_collect_blocking()
    # example_2_bm25_blocking()
    # example_3_batch_similarity()
    # example_4_detailed_similarity()
    # example_5_create_edges()
    # example_6_wcc_clustering()
    # example_7_validate_clusters()
    # example_8_complete_pipeline()
    
    print("\n" + "=" * 80)
    print("Uncomment examples in main() to run them")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

