#!/usr/bin/env python3
"""
Performance Optimization

This script implements caching and performance optimizations for the entity resolution system
to improve performance beyond the current 16K+ similarities/second.
"""

import sys
import os
import json
import time
import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from functools import lru_cache
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.clustering_service import ClusteringService
from entity_resolution.core.entity_resolver import EntityResolutionPipeline
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger

@dataclass
class CacheConfig:
    """Cache configuration."""
    max_size: int = 10000
    ttl_seconds: int = 3600  # 1 hour
    enable_similarity_cache: bool = True
    enable_blocking_cache: bool = True
    enable_clustering_cache: bool = True

class PerformanceOptimizer:
    """Performance optimization with caching and parallel processing."""
    
    def __init__(self, cache_config: Optional[CacheConfig] = None):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.cache_config = cache_config or CacheConfig()
        
        # Initialize services
        self.similarity_service = SimilarityService()
        self.blocking_service = BlockingService()
        self.clustering_service = ClusteringService()
        
        # Cache storage
        self.similarity_cache = {}
        self.blocking_cache = {}
        self.clustering_cache = {}
        
        # Cache metadata
        self.cache_metadata = {
            "similarity": {},
            "blocking": {},
            "clustering": {}
        }
        
        # Performance metrics
        self.performance_metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0,
            "average_response_time": 0.0,
            "throughput": 0.0
        }
    
    def _generate_cache_key(self, data: Any, prefix: str = "") -> str:
        """Generate cache key for data."""
        data_str = json.dumps(data, sort_keys=True)
        return f"{prefix}:{hashlib.md5(data_str.encode()).hexdigest()}"
    
    def _is_cache_valid(self, cache_key: str, cache_type: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self.cache_metadata[cache_type]:
            return False
        
        entry_time = self.cache_metadata[cache_type][cache_key]["timestamp"]
        return (datetime.now() - entry_time).seconds < self.cache_config.ttl_seconds
    
    def _get_from_cache(self, cache_key: str, cache_type: str) -> Optional[Any]:
        """Get value from cache."""
        if cache_type == "similarity" and cache_key in self.similarity_cache:
            if self._is_cache_valid(cache_key, cache_type):
                self.performance_metrics["cache_hits"] += 1
                return self.similarity_cache[cache_key]
            else:
                # Remove expired entry
                del self.similarity_cache[cache_key]
                del self.cache_metadata[cache_type][cache_key]
        
        elif cache_type == "blocking" and cache_key in self.blocking_cache:
            if self._is_cache_valid(cache_key, cache_type):
                self.performance_metrics["cache_hits"] += 1
                return self.blocking_cache[cache_key]
            else:
                del self.blocking_cache[cache_key]
                del self.cache_metadata[cache_type][cache_key]
        
        elif cache_type == "clustering" and cache_key in self.clustering_cache:
            if self._is_cache_valid(cache_key, cache_type):
                self.performance_metrics["cache_hits"] += 1
                return self.clustering_cache[cache_key]
            else:
                del self.clustering_cache[cache_key]
                del self.cache_metadata[cache_type][cache_key]
        
        self.performance_metrics["cache_misses"] += 1
        return None
    
    def _set_cache(self, cache_key: str, value: Any, cache_type: str):
        """Set value in cache."""
        current_time = datetime.now()
        
        if cache_type == "similarity":
            self.similarity_cache[cache_key] = value
            self.cache_metadata[cache_type][cache_key] = {"timestamp": current_time}
            
            # Cleanup if cache is too large
            if len(self.similarity_cache) > self.cache_config.max_size:
                oldest_key = min(self.cache_metadata[cache_type].keys(), 
                               key=lambda k: self.cache_metadata[cache_type][k]["timestamp"])
                del self.similarity_cache[oldest_key]
                del self.cache_metadata[cache_type][oldest_key]
        
        elif cache_type == "blocking":
            self.blocking_cache[cache_key] = value
            self.cache_metadata[cache_type][cache_key] = {"timestamp": current_time}
            
            if len(self.blocking_cache) > self.cache_config.max_size:
                oldest_key = min(self.cache_metadata[cache_type].keys(), 
                               key=lambda k: self.cache_metadata[cache_type][k]["timestamp"])
                del self.blocking_cache[oldest_key]
                del self.cache_metadata[cache_type][oldest_key]
        
        elif cache_type == "clustering":
            self.clustering_cache[cache_key] = value
            self.cache_metadata[cache_type][cache_key] = {"timestamp": current_time}
            
            if len(self.clustering_cache) > self.cache_config.max_size:
                oldest_key = min(self.cache_metadata[cache_type].keys(), 
                               key=lambda k: self.cache_metadata[cache_type][k]["timestamp"])
                del self.clustering_cache[oldest_key]
                del self.cache_metadata[cache_type][oldest_key]
    
    @lru_cache(maxsize=1000)
    def _cached_similarity_computation(self, doc_a_str: str, doc_b_str: str) -> Dict[str, Any]:
        """Cached similarity computation using LRU cache."""
        doc_a = json.loads(doc_a_str)
        doc_b = json.loads(doc_b_str)
        
        return self.similarity_service.compute_similarity(doc_a, doc_b)
    
    def optimized_similarity_computation(self, doc_a: Dict[str, Any], doc_b: Dict[str, Any]) -> Dict[str, Any]:
        """Optimized similarity computation with caching."""
        if not self.cache_config.enable_similarity_cache:
            return self.similarity_service.compute_similarity(doc_a, doc_b)
        
        # Generate cache key
        cache_key = self._generate_cache_key({"doc_a": doc_a, "doc_b": doc_b}, "similarity")
        
        # Check cache
        cached_result = self._get_from_cache(cache_key, "similarity")
        if cached_result is not None:
            return cached_result
        
        # Compute similarity
        result = self.similarity_service.compute_similarity(doc_a, doc_b)
        
        # Cache result
        self._set_cache(cache_key, result, "similarity")
        
        return result
    
    def optimized_blocking_generation(self, record: Dict[str, Any]) -> str:
        """Optimized blocking key generation with caching."""
        if not self.cache_config.enable_blocking_cache:
            return self.blocking_service._generate_blocking_key(record)
        
        # Generate cache key
        cache_key = self._generate_cache_key(record, "blocking")
        
        # Check cache
        cached_result = self._get_from_cache(cache_key, "blocking")
        if cached_result is not None:
            return cached_result
        
        # Generate blocking key
        blocking_key = self.blocking_service._generate_blocking_key(record)
        
        # Cache result
        self._set_cache(cache_key, blocking_key, "blocking")
        
        return blocking_key
    
    def optimized_clustering(self, similarity_pairs: List[Dict[str, Any]]) -> List[List[str]]:
        """Optimized clustering with caching."""
        if not self.cache_config.enable_clustering_cache:
            return self.clustering_service.cluster_entities(similarity_pairs)
        
        # Generate cache key
        cache_key = self._generate_cache_key(similarity_pairs, "clustering")
        
        # Check cache
        cached_result = self._get_from_cache(cache_key, "clustering")
        if cached_result is not None:
            return cached_result
        
        # Perform clustering
        clusters = self.clustering_service.cluster_entities(similarity_pairs)
        
        # Cache result
        self._set_cache(cache_key, clusters, "clustering")
        
        return clusters
    
    def parallel_similarity_computation(self, similarity_pairs: List[Dict[str, Any]], 
                                      max_workers: int = 4) -> List[Dict[str, Any]]:
        """Parallel similarity computation."""
        print(f"? Running parallel similarity computation with {max_workers} workers...")
        
        def compute_similarity_pair(pair_data):
            doc_a = pair_data["doc_a"]
            doc_b = pair_data["doc_b"]
            return self.optimized_similarity_computation(doc_a, doc_b)
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(compute_similarity_pair, similarity_pairs))
        
        execution_time = time.time() - start_time
        
        print(f"   ? Processed {len(similarity_pairs)} pairs in {execution_time:.3f}s")
        print(f"   ? Rate: {len(similarity_pairs)/execution_time:.1f} pairs/second")
        
        return results
    
    def batch_similarity_computation(self, similarity_pairs: List[Dict[str, Any]], 
                                   batch_size: int = 100) -> List[Dict[str, Any]]:
        """Batch similarity computation for better performance."""
        print(f"? Running batch similarity computation (batch size: {batch_size})...")
        
        results = []
        start_time = time.time()
        
        for i in range(0, len(similarity_pairs), batch_size):
            batch = similarity_pairs[i:i + batch_size]
            
            # Process batch
            batch_results = []
            for pair in batch:
                result = self.optimized_similarity_computation(pair["doc_a"], pair["doc_b"])
                batch_results.append(result)
            
            results.extend(batch_results)
            
            # Progress update
            if (i // batch_size + 1) % 10 == 0:
                elapsed = time.time() - start_time
                rate = (i + len(batch)) / elapsed
                print(f"   ? Processed {i + len(batch)}/{len(similarity_pairs)} pairs ({rate:.1f} pairs/s)")
        
        execution_time = time.time() - start_time
        
        print(f"   ? Completed {len(similarity_pairs)} pairs in {execution_time:.3f}s")
        print(f"   ? Rate: {len(similarity_pairs)/execution_time:.1f} pairs/second")
        
        return results
    
    def memory_optimized_processing(self, data: List[Dict[str, Any]], 
                                  chunk_size: int = 1000) -> List[Dict[str, Any]]:
        """Memory-optimized processing for large datasets."""
        print(f"? Running memory-optimized processing (chunk size: {chunk_size})...")
        
        results = []
        start_time = time.time()
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            
            # Process chunk
            chunk_results = []
            for item in chunk:
                # Process item (similarity computation, blocking, etc.)
                result = self.optimized_similarity_computation(item.get("doc_a", {}), item.get("doc_b", {}))
                chunk_results.append(result)
            
            results.extend(chunk_results)
            
            # Memory cleanup
            del chunk
            del chunk_results
            
            # Progress update
            if (i // chunk_size + 1) % 10 == 0:
                elapsed = time.time() - start_time
                rate = (i + len(chunk)) / elapsed
                print(f"   ? Processed {i + len(chunk)}/{len(data)} items ({rate:.1f} items/s)")
        
        execution_time = time.time() - start_time
        
        print(f"   ? Completed {len(data)} items in {execution_time:.3f}s")
        print(f"   ? Rate: {len(data)/execution_time:.1f} items/second")
        
        return results
    
    def benchmark_performance(self, test_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Benchmark performance optimizations."""
        print("? PERFORMANCE OPTIMIZATION BENCHMARKS")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        benchmark_results = {
            "timestamp": datetime.now().isoformat(),
            "test_data_size": len(test_data),
            "optimizations": {},
            "recommendations": []
        }
        
        # Test 1: Baseline (no optimizations)
        print("\n? Test 1: Baseline Performance")
        start_time = time.time()
        
        baseline_results = []
        for pair in test_data[:100]:  # Limit for benchmarking
            result = self.similarity_service.compute_similarity(pair["doc_a"], pair["doc_b"])
            baseline_results.append(result)
        
        baseline_time = time.time() - start_time
        baseline_rate = len(baseline_results) / baseline_time
        
        benchmark_results["optimizations"]["baseline"] = {
            "execution_time": baseline_time,
            "rate": baseline_rate,
            "description": "No optimizations"
        }
        
        print(f"   ? Baseline: {baseline_rate:.1f} pairs/second")
        
        # Test 2: Caching optimization
        print("\n? Test 2: Caching Optimization")
        start_time = time.time()
        
        cached_results = []
        for pair in test_data[:100]:
            result = self.optimized_similarity_computation(pair["doc_a"], pair["doc_b"])
            cached_results.append(result)
        
        cached_time = time.time() - start_time
        cached_rate = len(cached_results) / cached_time
        
        benchmark_results["optimizations"]["caching"] = {
            "execution_time": cached_time,
            "rate": cached_rate,
            "improvement": (cached_rate - baseline_rate) / baseline_rate * 100,
            "description": "With caching optimization"
        }
        
        print(f"   ? Caching: {cached_rate:.1f} pairs/second ({((cached_rate - baseline_rate) / baseline_rate * 100):+.1f}% improvement)")
        
        # Test 3: Parallel processing
        print("\n? Test 3: Parallel Processing")
        parallel_results = self.parallel_similarity_computation(test_data[:100], max_workers=4)
        
        benchmark_results["optimizations"]["parallel"] = {
            "description": "Parallel processing with 4 workers"
        }
        
        # Test 4: Batch processing
        print("\n? Test 4: Batch Processing")
        batch_results = self.batch_similarity_computation(test_data[:100], batch_size=50)
        
        benchmark_results["optimizations"]["batch"] = {
            "description": "Batch processing optimization"
        }
        
        # Test 5: Memory optimization
        print("\n? Test 5: Memory Optimization")
        memory_results = self.memory_optimized_processing(test_data[:100], chunk_size=50)
        
        benchmark_results["optimizations"]["memory"] = {
            "description": "Memory-optimized processing"
        }
        
        # Calculate cache statistics
        cache_hit_rate = self.performance_metrics["cache_hits"] / max(self.performance_metrics["total_requests"], 1)
        
        benchmark_results["cache_statistics"] = {
            "cache_hits": self.performance_metrics["cache_hits"],
            "cache_misses": self.performance_metrics["cache_misses"],
            "hit_rate": cache_hit_rate,
            "total_requests": self.performance_metrics["total_requests"]
        }
        
        print(f"\n? Cache Statistics:")
        print(f"   ? Cache hits: {self.performance_metrics['cache_hits']}")
        print(f"   ? Cache misses: {self.performance_metrics['cache_misses']}")
        print(f"   ? Hit rate: {cache_hit_rate:.1%}")
        
        # Generate recommendations
        recommendations = []
        
        if cached_rate > baseline_rate * 1.2:
            recommendations.append("[PASS] Caching provides significant performance improvement")
        else:
            recommendations.append("[WARN]?  Caching improvement is minimal - consider cache tuning")
        
        if cache_hit_rate > 0.5:
            recommendations.append("[PASS] Good cache hit rate - caching is effective")
        else:
            recommendations.append("[WARN]?  Low cache hit rate - consider cache key optimization")
        
        if len(test_data) > 1000:
            recommendations.append("[PASS] Use batch processing for large datasets")
        
        if len(test_data) > 10000:
            recommendations.append("[PASS] Use memory-optimized processing for very large datasets")
        
        benchmark_results["recommendations"] = recommendations
        
        # Save benchmark results
        report_file = f"performance_optimization_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(benchmark_results, f, indent=2, default=str)
        
        print(f"\n? Performance benchmark report saved: {report_file}")
        
        return benchmark_results
    
    def run_comprehensive_optimization(self) -> Dict[str, Any]:
        """Run comprehensive performance optimization analysis."""
        print("? COMPREHENSIVE PERFORMANCE OPTIMIZATION")
        print("="*70)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Generate test data
        test_data = []
        for i in range(1000):
            test_data.append({
                "doc_a": {
                    "first_name": f"John{i}",
                    "last_name": f"Smith{i}",
                    "email": f"john{i}@example.com",
                    "phone": f"555-{i:04d}"
                },
                "doc_b": {
                    "first_name": f"Jon{i}",
                    "last_name": f"Smith{i}",
                    "email": f"j{i}@example.com",
                    "phone": f"555-{i:04d}"
                }
            })
        
        # Run benchmarks
        benchmark_results = self.benchmark_performance(test_data)
        
        return benchmark_results

def main():
    """Run performance optimization analysis."""
    try:
        optimizer = PerformanceOptimizer()
        results = optimizer.run_comprehensive_optimization()
        return 0
    except Exception as e:
        print(f"[FAIL] Performance optimization failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
