#!/usr/bin/env python3
"""
Bulk Processing Demo

Demonstrates the performance difference between batch and bulk processing
for large-scale entity resolution.

Run this script to see:
1. Bulk processing of entire collection in single pass
2. Performance metrics and statistics
3. Comparison with traditional batch approach

Usage:
    python examples/bulk_processing_demo.py
    python examples/bulk_processing_demo.py --collection customers --strategies exact ngram
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from entity_resolution.services.bulk_blocking_service import BulkBlockingService
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

logger = get_logger(__name__)


def demo_bulk_processing(collection_name: str = "customers", 
                        strategies: list = None,
                        limit: int = 0):
    """
    Demonstrate bulk processing for large-scale entity resolution
    
    Args:
        collection_name: Name of collection to process
        strategies: Blocking strategies to use
        limit: Maximum pairs to generate (0 = no limit)
    """
    strategies = strategies or ["exact", "ngram"]
    
    print("=" * 80)
    print("BULK PROCESSING DEMO")
    print("=" * 80)
    print()
    
    # Initialize bulk blocking service
    print("[CONFIG] Initializing Bulk Blocking Service...")
    bulk_service = BulkBlockingService()
    
    if not bulk_service.connect():
        print("[ X ] Failed to connect to database")
        print()
        print("Authentication error. Please check your database credentials.")
        print("Set environment variables or update config.json:")
        print("  - DB_HOST (default: localhost)")
        print("  - DB_PORT (default: 8529)")
        print("  - DB_NAME (default: entity_resolution)")
        print("  - DB_USERNAME (default: root)")
        print("  - DB_PASSWORD (default: testpassword123)")
        print()
        return
    
    print("[OK] Connected to database")
    print()
    
    # Get collection statistics
    print("[CHART] Analyzing Collection...")
    stats = bulk_service.get_collection_stats(collection_name)
    
    if not stats["success"]:
        print(f"[ X ] Error: {stats['error']}")
        print()
        if "not authorized" in stats.get('error', '').lower():
            print("Authentication failed. Check your credentials:")
            print("  export DB_USERNAME=your_username")
            print("  export DB_PASSWORD=your_password")
            print("  export DB_NAME=your_database")
        return
    
    record_count = stats["record_count"]
    naive_comparisons = stats["naive_comparisons"]
    
    print(f"   Collection: {collection_name}")
    print(f"   Records: {record_count:,}")
    print(f"   Naive comparisons (without blocking): {naive_comparisons:,}")
    print()
    
    # Calculate time savings
    print("[TIME] Performance Estimation:")
    print(f"   Batch approach (row-by-row): ~{record_count * 0.12 / 60:.1f} minutes")
    print(f"   Bulk approach (set-based):   ~{record_count / 10000:.1f} minutes")
    print(f"   Expected speedup: {(record_count * 0.12 / 60) / (record_count / 10000):.1f}x faster")
    print()
    
    # Prompt user to continue for large datasets
    if record_count > 50000:
        response = input(f"[WARNING] Large dataset ({record_count:,} records). Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            return
        print()
    
    # Run bulk blocking
    print("[LAUNCH] Running Bulk Blocking...")
    print(f"   Strategies: {', '.join(strategies)}")
    print(f"   Limit: {'No limit (process all)' if limit == 0 else f'{limit:,} pairs'}")
    print()
    
    start_time = time.time()
    
    result = bulk_service.generate_all_pairs(
        collection_name=collection_name,
        strategies=strategies,
        limit=limit
    )
    
    elapsed_time = time.time() - start_time
    
    if not result["success"]:
        print(f"[ X ] Error: {result['error']}")
        return
    
    # Display results
    print("[OK] Bulk Blocking Complete!")
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    stats = result["statistics"]
    
    print(f"[GRAPH] Candidate Pairs Generated: {stats['total_pairs']:,}")
    print(f"   Before deduplication: {stats['total_pairs_before_dedup']:,}")
    print(f"   Duplicates removed: {stats['duplicate_pairs_removed']:,}")
    print()
    
    print("[FAST] Performance Metrics:")
    print(f"   Total execution time: {stats['execution_time']:.2f} seconds")
    print(f"   Pairs per second: {stats['pairs_per_second']:,}")
    print()
    
    print("[CHART] Strategy Breakdown:")
    for strategy, strategy_stats in stats['strategy_breakdown'].items():
        pairs = strategy_stats['pairs_found']
        exec_time = strategy_stats['execution_time']
        print(f"   {strategy:12s}: {pairs:8,} pairs in {exec_time:6.2f}s ({pairs/exec_time:,.0f} pairs/sec)")
    print()
    
    # Blocking efficiency
    if naive_comparisons > 0:
        blocking_efficiency = (1 - stats['total_pairs'] / naive_comparisons) * 100
        print(f"[TARGET] Blocking Efficiency: {blocking_efficiency:.2f}%")
        print(f"   (Reduced {naive_comparisons:,} comparisons to {stats['total_pairs']:,})")
        print()
    
    # Show sample pairs
    if result["candidate_pairs"]:
        print("[SEARCH] Sample Candidate Pairs (first 5):")
        for i, pair in enumerate(result["candidate_pairs"][:5], 1):
            print(f"   {i}. {pair['record_a_id']} <-> {pair['record_b_id']}")
            print(f"      Strategy: {pair['strategy']}, Key: {pair.get('blocking_key', 'N/A')}")
        
        if len(result["candidate_pairs"]) > 5:
            print(f"   ... and {len(result['candidate_pairs']) - 5:,} more pairs")
        print()
    
    # Performance comparison
    print("=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    print()
    
    # Estimated batch processing time
    estimated_batch_time = record_count * 0.12  # ~120ms per record with batch API
    speedup = estimated_batch_time / stats['execution_time']
    
    print("Batch Processing (old approach):")
    print(f"   Estimated time: {estimated_batch_time:.1f} seconds ({estimated_batch_time/60:.1f} minutes)")
    print(f"   API calls needed: {record_count / 100:.0f}")
    print(f"   Network overhead: {(record_count / 100) * 0.05:.1f} seconds")
    print()
    
    print("Bulk Processing (this run):")
    print(f"   Actual time: {stats['execution_time']:.1f} seconds ({stats['execution_time']/60:.1f} minutes)")
    print(f"   API calls needed: 1")
    print(f"   Network overhead: 0.05 seconds")
    print()
    
    print(f"[FAST] Speedup: {speedup:.1f}x faster with bulk processing!")
    print()
    
    # Next steps
    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("1. Use these pairs for similarity computation:")
    print(f"   similarity_service.compute_batch(pairs={len(result['candidate_pairs'])})")
    print()
    print("2. Cluster similar entities:")
    print("   clustering_service.cluster_entities(scored_pairs)")
    print()
    print("3. Generate golden records:")
    print("   golden_record_service.create_golden_records(clusters)")
    print()
    
    # Save results option
    save = input("[SAVE] Save results to file? [y/N]: ")
    if save.lower() == 'y':
        import json
        from datetime import datetime
        
        filename = f"bulk_blocking_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"[OK] Results saved to {filename}")
    print()


def demo_streaming_processing(collection_name: str = "customers", batch_size: int = 1000):
    """
    Demonstrate streaming processing for very large datasets
    
    Args:
        collection_name: Name of collection
        batch_size: Number of pairs to process at a time
    """
    print("=" * 80)
    print("STREAMING PROCESSING DEMO")
    print("=" * 80)
    print()
    
    bulk_service = BulkBlockingService()
    
    if not bulk_service.connect():
        print("[ X ] Failed to connect to database")
        return
    
    print("[OK] Connected to database")
    print()
    print("[LAUNCH] Streaming candidate pairs...")
    print(f"   Batch size: {batch_size:,} pairs")
    print()
    
    total_pairs = 0
    batch_count = 0
    start_time = time.time()
    
    for batch in bulk_service.generate_pairs_streaming(
        collection_name=collection_name,
        strategies=["exact", "ngram"],
        batch_size=batch_size
    ):
        batch_count += 1
        total_pairs += len(batch)
        
        # Process batch (in real application, this would be similarity scoring)
        print(f"   Batch {batch_count}: {len(batch):,} pairs (total: {total_pairs:,})")
        
        # Simulate processing time
        time.sleep(0.1)
    
    elapsed_time = time.time() - start_time
    
    print()
    print(f"[OK] Streaming complete!")
    print(f"   Total pairs: {total_pairs:,}")
    print(f"   Batches processed: {batch_count}")
    print(f"   Time: {elapsed_time:.2f} seconds")
    print()


def main():
    """Main demo function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bulk Processing Demo")
    parser.add_argument(
        "--collection",
        default="customers",
        help="Collection name to process"
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["exact", "ngram"],
        choices=["exact", "ngram", "phonetic"],
        help="Blocking strategies to use"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum pairs to generate (0 = no limit)"
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Use streaming mode"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for streaming mode"
    )
    
    args = parser.parse_args()
    
    try:
        if args.streaming:
            demo_streaming_processing(args.collection, args.batch_size)
        else:
            demo_bulk_processing(args.collection, args.strategies, args.limit)
    except KeyboardInterrupt:
        print("\n\n[WARNING] Interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n[ X ] Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

