#!/usr/bin/env python3
"""
Lightweight performance micro-benchmark for LSH Blocking Strategy.

This script benchmarks LSH blocking performance with different configurations:
- Different numbers of hash tables (L)
- Different numbers of hyperplanes (k)
- Different dataset sizes

NOT RUN IN CI - for manual performance testing only.

Usage:
    python scripts/benchmark_lsh_blocking.py
"""

import sys
import os
import time
import numpy as np
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.strategies.lsh_blocking import LSHBlockingStrategy


class MockAQL:
    """Mock AQL executor for benchmarking."""
    
    def __init__(self, documents: List[Dict[str, Any]]):
        self.documents = documents
    
    def execute(self, query: str, bind_vars: Dict[str, Any] = None):
        """Mock AQL execution."""
        if "RETURN {" in query and "embedding" in query and "blocking_value" in query:
            return iter(self.documents)
        elif "RETURN {" in query and "total" in query:
            # Return stats query result
            return iter([{
                'total': len(self.documents),
                'with_embeddings': len([d for d in self.documents if d.get('embedding') is not None]),
                'without_embeddings': len([d for d in self.documents if d.get('embedding') is None]),
                'coverage_percent': 100.0 if self.documents else 0.0,
                'embedding_dim': len(self.documents[0]['embedding']) if self.documents and self.documents[0].get('embedding') else None
            }])
        return iter([])


class MockDB:
    """Mock database for benchmarking."""
    
    def __init__(self, documents: List[Dict[str, Any]]):
        self.aql = MockAQL(documents)


def generate_synthetic_embeddings(
    num_documents: int,
    embedding_dim: int = 384,
    num_clusters: int = 10,
    cluster_noise: float = 0.2,
    seed: int = 42
) -> List[np.ndarray]:
    """
    Generate synthetic embeddings with known clusters.
    
    Args:
        num_documents: Number of documents to generate
        embedding_dim: Dimension of embeddings (default: 384)
        num_clusters: Number of clusters (groups of similar documents)
        cluster_noise: Noise level within clusters (0-1)
        seed: Random seed
        
    Returns:
        List of embedding vectors
    """
    rng = np.random.RandomState(seed)
    
    # Generate cluster centers
    cluster_centers = []
    for _ in range(num_clusters):
        center = rng.randn(embedding_dim)
        center = center / np.linalg.norm(center)
        cluster_centers.append(center)
    
    # Generate documents around cluster centers
    embeddings = []
    docs_per_cluster = num_documents // num_clusters
    
    for cluster_idx, center in enumerate(cluster_centers):
        for _ in range(docs_per_cluster):
            # Add noise to cluster center
            vector = center + cluster_noise * rng.randn(embedding_dim)
            vector = vector / np.linalg.norm(vector)
            embeddings.append(vector)
    
    # Add remaining documents randomly
    for _ in range(num_documents - len(embeddings)):
        vector = rng.randn(embedding_dim)
        vector = vector / np.linalg.norm(vector)
        embeddings.append(vector)
    
    return embeddings


def create_documents(embeddings: List[np.ndarray]) -> List[Dict[str, Any]]:
    """Convert embeddings to document format."""
    documents = []
    for i, embedding in enumerate(embeddings):
        documents.append({
            '_key': f'doc_{i:06d}',
            'embedding': embedding.tolist()
        })
    return documents


def benchmark_configuration(
    num_documents: int,
    num_hash_tables: int,
    num_hyperplanes: int,
    embedding_dim: int = 384,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Benchmark a specific LSH configuration.
    
    Returns:
        Dictionary with benchmark results
    """
    # Generate synthetic data
    embeddings = generate_synthetic_embeddings(
        num_documents=num_documents,
        embedding_dim=embedding_dim,
        seed=seed
    )
    documents = create_documents(embeddings)
    
    # Create mock database
    mock_db = MockDB(documents)
    
    # Create strategy
    strategy = LSHBlockingStrategy(
        db=mock_db,
        collection="benchmark_collection",
        num_hash_tables=num_hash_tables,
        num_hyperplanes=num_hyperplanes,
        random_seed=seed
    )
    
    # Benchmark
    start_time = time.time()
    pairs = strategy.generate_candidates()
    execution_time = time.time() - start_time
    
    stats = strategy.get_statistics()
    
    return {
        'num_documents': num_documents,
        'num_hash_tables': num_hash_tables,
        'num_hyperplanes': num_hyperplanes,
        'num_pairs': len(pairs),
        'execution_time_seconds': execution_time,
        'pairs_per_second': len(pairs) / execution_time if execution_time > 0 else 0,
        'stats': stats
    }


def run_benchmarks():
    """Run comprehensive benchmarks."""
    print("=" * 80)
    print("LSH Blocking Strategy Performance Benchmark")
    print("=" * 80)
    print()
    
    # Test configurations
    configurations = [
        # (num_documents, num_hash_tables, num_hyperplanes)
        (100, 5, 4),
        (100, 10, 8),
        (100, 20, 16),
        (500, 5, 4),
        (500, 10, 8),
        (500, 20, 16),
        (1000, 5, 4),
        (1000, 10, 8),
        (1000, 20, 16),
        (5000, 10, 8),
        (10000, 10, 8),
    ]
    
    results = []
    
    print("Running benchmarks...")
    print()
    
    for num_docs, num_tables, num_hyperplanes in configurations:
        print(f"  Testing: {num_docs} docs, L={num_tables}, k={num_hyperplanes}...", end=' ', flush=True)
        
        try:
            result = benchmark_configuration(
                num_documents=num_docs,
                num_hash_tables=num_tables,
                num_hyperplanes=num_hyperplanes
            )
            results.append(result)
            print(f"✓ ({result['execution_time_seconds']:.2f}s, {result['num_pairs']} pairs)")
        except Exception as e:
            print(f"✗ Error: {e}")
            results.append({
                'num_documents': num_docs,
                'num_hash_tables': num_tables,
                'num_hyperplanes': num_hyperplanes,
                'error': str(e)
            })
    
    print()
    print("=" * 80)
    print("Benchmark Results")
    print("=" * 80)
    print()
    
    # Print results table
    print(f"{'Docs':<8} {'L':<4} {'k':<4} {'Pairs':<10} {'Time (s)':<12} {'Pairs/s':<12}")
    print("-" * 80)
    
    for result in results:
        if 'error' in result:
            print(f"{result['num_documents']:<8} {result['num_hash_tables']:<4} "
                  f"{result['num_hyperplanes']:<4} {'ERROR':<10}")
        else:
            print(f"{result['num_documents']:<8} {result['num_hash_tables']:<4} "
                  f"{result['num_hyperplanes']:<4} {result['num_pairs']:<10} "
                  f"{result['execution_time_seconds']:<12.2f} "
                  f"{result['pairs_per_second']:<12.0f}")
    
    print()
    print("=" * 80)
    print("Analysis")
    print("=" * 80)
    print()
    
    # Analyze scaling
    print("Scaling Analysis:")
    print()
    
    # Compare different L values with same dataset size
    for num_docs in [100, 500, 1000]:
        relevant = [r for r in results if r.get('num_documents') == num_docs and 'error' not in r]
        if len(relevant) >= 2:
            print(f"  {num_docs} documents:")
            for r in sorted(relevant, key=lambda x: x['num_hash_tables']):
                print(f"    L={r['num_hash_tables']}, k={r['num_hyperplanes']}: "
                      f"{r['num_pairs']} pairs in {r['execution_time_seconds']:.2f}s")
            print()
    
    # Compare different dataset sizes with same L/k
    print("Dataset Size Scaling:")
    print()
    for num_tables, num_hyperplanes in [(10, 8)]:
        relevant = [r for r in results 
                    if r.get('num_hash_tables') == num_tables 
                    and r.get('num_hyperplanes') == num_hyperplanes 
                    and 'error' not in r]
        if len(relevant) >= 2:
            print(f"  L={num_tables}, k={num_hyperplanes}:")
            for r in sorted(relevant, key=lambda x: x['num_documents']):
                print(f"    {r['num_documents']} docs: "
                      f"{r['num_pairs']} pairs in {r['execution_time_seconds']:.2f}s "
                      f"({r['pairs_per_second']:.0f} pairs/s)")
            print()
    
    print("=" * 80)
    print("Benchmark Complete")
    print("=" * 80)


if __name__ == '__main__':
    run_benchmarks()
