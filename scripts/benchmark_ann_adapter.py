#!/usr/bin/env python3
"""
Performance Micro-Benchmark for ANN Adapter

Compares performance of ANN adapter methods:
- ArangoDB native vector search (if available)
- Brute-force cosine similarity

This script is NOT run in CI - it's for manual performance testing.

Usage:
    python scripts/benchmark_ann_adapter.py [--collection COLLECTION] [--size SIZE]
"""

import argparse
import time
import sys
import os
from typing import List, Dict, Any
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from entity_resolution.similarity.ann_adapter import ANNAdapter
    from entity_resolution.services.embedding_service import EmbeddingService
    from entity_resolution.utils.database import get_database
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the project root and dependencies are installed.")
    sys.exit(1)


def generate_test_data(
    db,
    collection_name: str,
    num_docs: int,
    embedding_dim: int = 384
) -> None:
    """Generate test data with embeddings"""
    print(f"\n{'='*60}")
    print(f"Generating test data: {num_docs} documents")
    print(f"{'='*60}")
    
    # Create collection if needed
    if db.has_collection(collection_name):
        db.delete_collection(collection_name)
    
    collection = db.create_collection(collection_name)
    
    # Generate documents
    documents = []
    for i in range(num_docs):
        doc = {
            '_key': f'doc_{i:06d}',
            'name': f'Test User {i}',
            'company': f'Company {i % 100}',
            'city': f'City {i % 50}',
            'category': chr(65 + (i % 26))  # A-Z
        }
        documents.append(doc)
    
    # Insert documents
    collection.insert_many(documents)
    print(f"✓ Inserted {num_docs} documents")
    
    # Generate embeddings
    print("Generating embeddings...")
    embedding_service = EmbeddingService(
        model_name='all-MiniLM-L6-v2',
        device='cpu'
    )
    
    stats = embedding_service.ensure_embeddings_exist(
        collection_name,
        text_fields=['name', 'company', 'city'],
        database_name=db.name
    )
    
    print(f"✓ Generated {stats['generated']} embeddings")
    print(f"✓ Updated {stats['updated']} documents")
    
    return collection_name


def benchmark_single_query(
    adapter: ANNAdapter,
    query_vector: List[float],
    similarity_threshold: float,
    limit: int,
    num_runs: int = 5
) -> Dict[str, Any]:
    """Benchmark single query performance"""
    times = []
    
    for _ in range(num_runs):
        start = time.time()
        results = adapter.find_similar_vectors(
            query_vector=query_vector,
            similarity_threshold=similarity_threshold,
            limit=limit
        )
        elapsed = time.time() - start
        times.append(elapsed)
    
    return {
        'method': adapter.method,
        'num_results': len(results) if times else 0,
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'max_time': np.max(times),
        'times': times
    }


def benchmark_all_pairs(
    adapter: ANNAdapter,
    similarity_threshold: float,
    limit_per_entity: int,
    num_runs: int = 3
) -> Dict[str, Any]:
    """Benchmark all-pairs generation performance"""
    times = []
    num_pairs = []
    
    for _ in range(num_runs):
        start = time.time()
        pairs = adapter.find_all_pairs(
            similarity_threshold=similarity_threshold,
            limit_per_entity=limit_per_entity
        )
        elapsed = time.time() - start
        times.append(elapsed)
        num_pairs.append(len(pairs))
    
    return {
        'method': adapter.method,
        'mean_pairs': np.mean(num_pairs),
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'min_time': np.min(times),
        'max_time': np.max(times),
        'pairs_per_second': np.mean(num_pairs) / np.mean(times) if np.mean(times) > 0 else 0,
        'times': times,
        'num_pairs': num_pairs
    }


def print_results(results: Dict[str, Any], title: str):
    """Print benchmark results in a formatted way"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Method: {results['method']}")
    
    if 'num_results' in results:
        print(f"Results returned: {results['num_results']}")
    
    if 'mean_pairs' in results:
        print(f"Pairs generated: {results['mean_pairs']:.0f}")
        print(f"Pairs per second: {results['pairs_per_second']:.2f}")
    
    print(f"\nTiming (seconds):")
    print(f"  Mean:  {results['mean_time']:.4f}")
    print(f"  Std:   {results['std_time']:.4f}")
    print(f"  Min:   {results['min_time']:.4f}")
    print(f"  Max:   {results['max_time']:.4f}")
    
    if len(results.get('times', [])) > 1:
        print(f"\nIndividual runs: {[f'{t:.4f}' for t in results['times']]}")


def compare_methods(
    db,
    collection_name: str,
    dataset_size: int
):
    """Compare performance of different methods"""
    print(f"\n{'='*60}")
    print(f"ANN Adapter Performance Benchmark")
    print(f"{'='*60}")
    print(f"Collection: {collection_name}")
    print(f"Dataset size: {dataset_size} documents")
    
    # Get a query vector
    collection = db.collection(collection_name)
    sample_doc = collection.get('doc_000000')
    query_vector = sample_doc['embedding_vector']
    
    # Test 1: Single query performance
    print(f"\n{'='*60}")
    print("Test 1: Single Query Performance")
    print(f"{'='*60}")
    print("Finding similar vectors for a single query...")
    
    # Brute-force method
    adapter_bf = ANNAdapter(
        db=db,
        collection=collection_name,
        force_brute_force=True
    )
    
    results_bf = benchmark_single_query(
        adapter=adapter_bf,
        query_vector=query_vector,
        similarity_threshold=0.7,
        limit=20,
        num_runs=5
    )
    print_results(results_bf, "Brute-Force Method")
    
    # Auto-detection method
    adapter_auto = ANNAdapter(
        db=db,
        collection=collection_name,
        force_brute_force=False
    )
    
    results_auto = benchmark_single_query(
        adapter=adapter_auto,
        query_vector=query_vector,
        similarity_threshold=0.7,
        limit=20,
        num_runs=5
    )
    print_results(results_auto, "Auto-Detection Method")
    
    # Compare
    if results_bf['mean_time'] > 0:
        speedup = results_bf['mean_time'] / results_auto['mean_time']
        print(f"\n{'='*60}")
        print("Comparison:")
        print(f"{'='*60}")
        print(f"Speedup: {speedup:.2f}x ({'faster' if speedup > 1 else 'slower'})")
        print(f"Brute-force: {results_bf['mean_time']:.4f}s")
        print(f"Auto:        {results_auto['mean_time']:.4f}s")
    
    # Test 2: All-pairs generation
    print(f"\n{'='*60}")
    print("Test 2: All-Pairs Generation Performance")
    print(f"{'='*60}")
    print("Generating all candidate pairs...")
    
    # Only test brute-force for all-pairs (more predictable)
    results_pairs = benchmark_all_pairs(
        adapter=adapter_bf,
        similarity_threshold=0.7,
        limit_per_entity=20,
        num_runs=3
    )
    print_results(results_pairs, "All-Pairs Generation (Brute-Force)")
    
    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"Dataset size: {dataset_size} documents")
    print(f"Brute-force method: {adapter_bf.method}")
    print(f"Auto-detection method: {adapter_auto.method}")
    
    if results_bf['mean_time'] > 0 and results_auto['mean_time'] > 0:
        print(f"\nSingle query performance:")
        print(f"  Brute-force: {results_bf['mean_time']:.4f}s")
        print(f"  Auto:        {results_auto['mean_time']:.4f}s")
        print(f"  Speedup:     {results_bf['mean_time'] / results_auto['mean_time']:.2f}x")
    
    print(f"\nAll-pairs generation:")
    print(f"  Time:        {results_pairs['mean_time']:.4f}s")
    print(f"  Pairs:       {results_pairs['mean_pairs']:.0f}")
    print(f"  Throughput:  {results_pairs['pairs_per_second']:.2f} pairs/sec")


def main():
    """Main benchmark function"""
    parser = argparse.ArgumentParser(
        description='Benchmark ANN adapter performance'
    )
    parser.add_argument(
        '--collection',
        type=str,
        default='benchmark_ann_adapter',
        help='Collection name for benchmarking (default: benchmark_ann_adapter)'
    )
    parser.add_argument(
        '--size',
        type=int,
        default=1000,
        help='Number of documents to generate (default: 1000)'
    )
    parser.add_argument(
        '--no-setup',
        action='store_true',
        help='Skip data generation (use existing collection)'
    )
    
    args = parser.parse_args()
    
    # Get database connection
    try:
        db = get_database()
        print(f"✓ Connected to database: {db.name}")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Generate test data if needed
    if not args.no_setup:
        try:
            generate_test_data(db, args.collection, args.size)
        except Exception as e:
            print(f"✗ Failed to generate test data: {e}")
            sys.exit(1)
    else:
        if not db.has_collection(args.collection):
            print(f"✗ Collection '{args.collection}' does not exist")
            print("  Use --no-setup=false to generate test data")
            sys.exit(1)
        print(f"✓ Using existing collection: {args.collection}")
    
    # Run benchmarks
    try:
        compare_methods(db, args.collection, args.size)
    except Exception as e:
        print(f"✗ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print("Benchmark complete!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
