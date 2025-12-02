#!/usr/bin/env python3
"""
Cross-Collection Matching Examples

This file demonstrates the new cross-collection matching capabilities
extracted from the dnb_er customer project and generalized for the library.

Examples include:
1. Cross-collection matching (registrations → companies)
2. Hybrid blocking (BM25 + Levenshtein)
3. Geographic blocking (state, city, ZIP)
4. Graph traversal blocking (shared relationships)
5. Pipeline utilities (cleaning, statistics)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from entity_resolution.services.cross_collection_matching_service import CrossCollectionMatchingService
from entity_resolution.strategies.hybrid_blocking import HybridBlockingStrategy
from entity_resolution.strategies.geographic_blocking import GeographicBlockingStrategy
from entity_resolution.strategies.graph_traversal_blocking import GraphTraversalBlockingStrategy
from entity_resolution.utils.pipeline_utils import (
    clean_er_results,
    count_inferred_edges,
    validate_edge_quality,
    get_pipeline_statistics
)
from entity_resolution.utils.database import DatabaseManager


def example_1_cross_collection_matching():
    """
    Example 1: Match registrations to companies across collections.
    
    Scenario: You have a registrations collection and a companies collection.
    Some registrations don't have explicit company IDs. Use fuzzy matching
    to link them based on name and address.
    """
    print("=" * 80)
    print("Example 1: Cross-Collection Matching (Registrations → Companies)")
    print("=" * 80)
    
    # Setup database connection
    db_manager = DatabaseManager()
    db_manager.connect()
    db = db_manager.db
    
    # Create service
    service = CrossCollectionMatchingService(
        db=db,
        source_collection="registrations",
        target_collection="companies",
        edge_collection="hasCompany",
        search_view="companies_search"  # Optional: for BM25 speed boost
    )
    
    # Configure matching
    service.configure_matching(
        source_fields={
            "name": "company_name",        # Source field names
            "address": "address_line1",
            "city": "city"
        },
        target_fields={
            "name": "legal_name",          # Target field names
            "address": "street_address",
            "city": "location_city"
        },
        field_weights={
            "name": 0.6,                   # Name is most important
            "address": 0.3,
            "city": 0.1
        },
        blocking_fields=["state"],         # Only match within same state
        custom_filters={
            "source": {
                "company_name": {"not_null": True, "min_length": 3}
            },
            "target": {
                "legal_name": {"not_null": True}
            }
        }
    )
    
    # Run matching
    print("\nRunning cross-collection matching...")
    results = service.match_entities(
        threshold=0.85,                    # High confidence matches only
        batch_size=100,
        use_bm25=True,                     # Use BM25 for speed (if view exists)
        mark_as_inferred=True              # Mark edges as inferred
    )
    
    print(f"\n✅ Results:")
    print(f"   Edges created: {results['edges_created']:,}")
    print(f"   Candidates evaluated: {results['candidates_evaluated']:,}")
    print(f"   Source records processed: {results['source_records_processed']:,}")
    print(f"   Execution time: {results['execution_time_seconds']:.2f}s")
    
    # Get statistics
    stats = count_inferred_edges(db, "hasCompany")
    print(f"\n📊 Edge Statistics:")
    print(f"   Total edges: {stats['total_edges']:,}")
    print(f"   Inferred edges: {stats['inferred_edges']:,}")
    print(f"   Average confidence: {stats['avg_confidence']:.4f}")
    
    db_manager.disconnect()


def example_2_hybrid_blocking():
    """
    Example 2: Use hybrid BM25 + Levenshtein blocking for fast, accurate matching.
    
    Scenario: Deduplicate a large company database. BM25 provides fast initial
    filtering, Levenshtein ensures accuracy.
    """
    print("\n" + "=" * 80)
    print("Example 2: Hybrid BM25 + Levenshtein Blocking")
    print("=" * 80)
    
    db_manager = DatabaseManager()
    db_manager.connect()
    db = db_manager.db
    
    # Create hybrid strategy
    strategy = HybridBlockingStrategy(
        db=db,
        collection="companies",
        search_view="companies_search",
        search_fields={
            "company_name": 0.6,
            "ceo_name": 0.4
        },
        levenshtein_threshold=0.85,        # Final quality gate
        bm25_threshold=2.0,                # Initial filtering
        bm25_weight=0.2,                   # 20% BM25, 80% Levenshtein
        blocking_field="state"             # Only match within state
    )
    
    print("\nGenerating candidates with hybrid blocking...")
    pairs = strategy.generate_candidates()
    
    print(f"\n✅ Results:")
    print(f"   Candidate pairs: {len(pairs):,}")
    
    # Show sample results
    if pairs:
        print(f"\n📋 Sample Matches:")
        for i, pair in enumerate(pairs[:3], 1):
            print(f"   {i}. {pair['doc1_key']} ↔ {pair['doc2_key']}")
            print(f"      Levenshtein: {pair['levenshtein_score']:.4f}")
            print(f"      BM25: {pair['bm25_score']:.2f}")
            print(f"      Combined: {pair['combined_score']:.4f}")
            if 'field_scores' in pair:
                print(f"      Field scores: {pair['field_scores']}")
    
    # Get statistics
    stats = strategy.get_statistics()
    print(f"\n📊 Strategy Statistics:")
    print(f"   Avg Levenshtein score: {stats.get('avg_levenshtein_score', 0):.4f}")
    print(f"   Avg BM25 score: {stats.get('avg_bm25_score', 0):.2f}")
    
    db_manager.disconnect()


def example_3_geographic_blocking():
    """
    Example 3: Use geographic blocking for location-based matching.
    
    Scenario: Match businesses within cities or ZIP code ranges.
    Useful for regional deduplication.
    """
    print("\n" + "=" * 80)
    print("Example 3: Geographic Blocking")
    print("=" * 80)
    
    db_manager = DatabaseManager()
    db_manager.connect()
    db = db_manager.db
    
    # Example 3a: City + State blocking
    print("\n3a. City + State Blocking")
    strategy = GeographicBlockingStrategy(
        db=db,
        collection="businesses",
        blocking_type="city_state",
        geographic_fields={
            "city": "primary_city",
            "state": "primary_state"
        },
        filters={
            "primary_city": {"not_null": True},
            "primary_state": {"not_null": True}
        }
    )
    
    pairs = strategy.generate_candidates()
    print(f"   Candidate pairs: {len(pairs):,}")
    
    # Example 3b: ZIP range blocking (e.g., South Dakota)
    print("\n3b. ZIP Range Blocking (South Dakota: 570-577)")
    strategy = GeographicBlockingStrategy(
        db=db,
        collection="registrations",
        blocking_type="zip_range",
        geographic_fields={"zip": "postal_code"},
        zip_ranges=[("570", "577")],      # SD ZIP codes
        filters={"postal_code": {"not_null": True}}
    )
    
    pairs = strategy.generate_candidates()
    print(f"   Candidate pairs: {len(pairs):,}")
    
    # Show sample
    if pairs:
        print(f"\n📋 Sample ZIP Range Matches:")
        for i, pair in enumerate(pairs[:2], 1):
            print(f"   {i}. {pair['doc1_key']} ↔ {pair['doc2_key']}")
            print(f"      Blocking keys: {pair['blocking_keys']}")
            print(f"      Block size: {pair['block_size']}")
    
    db_manager.disconnect()


def example_4_graph_traversal_blocking():
    """
    Example 4: Use graph traversal to find entities sharing relationships.
    
    Scenario: Find companies sharing phone numbers or addresses.
    Entities with common relationships are likely duplicates.
    """
    print("\n" + "=" * 80)
    print("Example 4: Graph Traversal Blocking (Shared Relationships)")
    print("=" * 80)
    
    db_manager = DatabaseManager()
    db_manager.connect()
    db = db_manager.db
    
    # Example 4a: Find companies sharing phone numbers
    print("\n4a. Companies Sharing Phone Numbers")
    strategy = GraphTraversalBlockingStrategy(
        db=db,
        collection="companies",
        edge_collection="hasTelephone",
        intermediate_collection="telephone",
        direction="INBOUND",
        filters={
            "_key": {"not_equal": ["0", "0000000000", "9999999999"]}
        }
    )
    
    pairs = strategy.generate_candidates()
    print(f"   Candidate pairs: {len(pairs):,}")
    
    # Show sample
    if pairs:
        print(f"\n📋 Sample Phone-Based Matches:")
        for i, pair in enumerate(pairs[:2], 1):
            print(f"   {i}. {pair['doc1_key']} ↔ {pair['doc2_key']}")
            print(f"      Shared phone: {pair['shared_node_key']}")
            print(f"      Total companies with this phone: {pair['node_degree']}")
    
    # Example 4b: Find businesses at same address
    print("\n4b. Businesses Sharing Addresses")
    strategy = GraphTraversalBlockingStrategy(
        db=db,
        collection="businesses",
        edge_collection="hasAddress",
        intermediate_collection="addresses",
        direction="INBOUND",
        max_entities_per_node=20          # Avoid large office buildings
    )
    
    pairs = strategy.generate_candidates()
    print(f"   Candidate pairs: {len(pairs):,}")
    
    stats = strategy.get_statistics()
    print(f"\n📊 Graph Statistics:")
    print(f"   Unique shared addresses: {stats.get('unique_shared_nodes', 0):,}")
    print(f"   Avg businesses per address: {stats.get('avg_node_degree', 0):.2f}")
    
    db_manager.disconnect()


def example_5_pipeline_utilities():
    """
    Example 5: Use pipeline utilities for workflow management.
    
    Scenario: Clean previous results, validate edge quality, and
    get comprehensive statistics.
    """
    print("\n" + "=" * 80)
    print("Example 5: Pipeline Utilities")
    print("=" * 80)
    
    db_manager = DatabaseManager()
    db_manager.connect()
    db = db_manager.db
    
    # Clean previous results
    print("\n5a. Clean Previous ER Results")
    clean_results = clean_er_results(
        db,
        collections=["similarTo", "entity_clusters"],
        keep_last_n=5  # Keep only last 5 runs
    )
    
    for coll, count in clean_results['removed_counts'].items():
        print(f"   Removed {count:,} old records from {coll}")
    
    # Validate edge quality
    print("\n5b. Validate Edge Quality")
    validation = validate_edge_quality(
        db,
        edge_collection="similarTo",
        min_confidence=0.75
    )
    
    print(f"   Valid: {validation['valid']}")
    print(f"   Total edges: {validation['total_edges']:,}")
    print(f"   Valid edges: {validation['valid_edges']:,}")
    print(f"   Invalid edges: {validation['invalid_edges']:,}")
    
    if validation['issues']:
        print(f"\n   Issues found:")
        for issue in validation['issues']:
            print(f"      - {issue['type']}: {issue['count']} ({issue['severity']})")
    
    # Get comprehensive statistics
    print("\n5c. Comprehensive Pipeline Statistics")
    stats = get_pipeline_statistics(
        db,
        vertex_collection="companies",
        edge_collection="similarTo",
        cluster_collection="entity_clusters"
    )
    
    print(f"\n📊 Entity Statistics:")
    if 'entities' in stats:
        print(f"   Total entities: {stats['entities']['total']:,}")
        print(f"   Clustered: {stats['entities']['clustered']:,}")
        print(f"   Clustering rate: {stats['entities']['clustering_rate']:.2%}")
    
    print(f"\n📊 Edge Statistics:")
    if 'edges' in stats:
        print(f"   Total edges: {stats['edges']['total']:,}")
        print(f"   Inferred: {stats['edges']['inferred']:,}")
        print(f"   Average confidence: {stats['edges']['avg_confidence']:.4f}")
    
    print(f"\n📊 Cluster Statistics:")
    if 'clusters' in stats:
        print(f"   Total clusters: {stats['clusters']['total']:,}")
        print(f"   Average cluster size: {stats['clusters']['avg_size']:.2f}")
        print(f"   Max cluster size: {stats['clusters']['max_size']}")
        if stats['clusters']['size_distribution']:
            print(f"   Size distribution:")
            for size_range, count in stats['clusters']['size_distribution'].items():
                print(f"      {size_range}: {count:,} clusters")
    
    print(f"\n📊 Performance Metrics:")
    if 'performance' in stats:
        print(f"   Pairs reduction: {stats['performance']['pairs_reduction']}")
        print(f"   Match rate: {stats['performance']['match_rate']}")
    
    db_manager.disconnect()


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("CROSS-COLLECTION MATCHING AND ADVANCED ER EXAMPLES")
    print("=" * 80)
    print("\nThese examples demonstrate features extracted from the dnb_er")
    print("customer project and generalized for the library.")
    print("\nNote: Examples require appropriate collections and data to be present.")
    print("      Modify collection names and fields for your specific use case.")
    print("=" * 80)
    
    try:
        # Run examples
        # Note: Comment out examples that don't apply to your dataset
        
        # example_1_cross_collection_matching()
        # example_2_hybrid_blocking()
        # example_3_geographic_blocking()
        # example_4_graph_traversal_blocking()
        # example_5_pipeline_utilities()
        
        print("\n" + "=" * 80)
        print("✅ Examples completed successfully!")
        print("=" * 80)
        print("\nTo run these examples with your data:")
        print("1. Modify collection names to match your database")
        print("2. Update field names to match your schema")
        print("3. Adjust thresholds and parameters as needed")
        print("4. Uncomment the example functions above")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

