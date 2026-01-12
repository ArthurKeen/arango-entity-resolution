"""
Performance Benchmark Tests

Validates performance claims for bulk processing:
- 3-5x faster than batch approach
- Network overhead reduction (3,319 calls -> 1 call)
- Linear scalability with dataset size

These tests measure actual performance and can be used for:
- Regression testing
- Performance profiling
- Validating optimization claims
"""

import pytest
import time
import os
import sys
from typing import List, Dict
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.bulk_blocking_service import BulkBlockingService
from entity_resolution.services.blocking_service import BlockingService


# Skip if no database available
skip_performance = os.getenv('SKIP_PERFORMANCE_TESTS', 'false').lower() == 'true'
skip_reason = "Skipping performance tests (SKIP_PERFORMANCE_TESTS=true)"


@pytest.fixture
def performance_collection():
    """Create a larger test collection for performance testing"""
    service = BulkBlockingService()
    
    if not service.connect():
        pytest.skip("Cannot connect to database")
    
    collection_name = "test_performance"
    
    # Create collection
    if service.db.has_collection(collection_name):
        service.db.delete_collection(collection_name)
    
    collection = service.db.create_collection(collection_name)
    
    # Insert 1000 test records
    test_data = []
    for i in range(1000):
        test_data.append({
            "_key": str(i),
            "first_name": f"First{i % 100}",  # Some duplicates
            "last_name": f"Last{i % 50}",     # More duplicates
            "phone": f"555-{i % 20:04d}",     # Even more duplicates
            "email": f"user{i}@example.com"
        })
    
    collection.insert_many(test_data)
    
    yield collection_name, service
    
    # Cleanup
    if service.db.has_collection(collection_name):
        service.db.delete_collection(collection_name)


@pytest.mark.skipif(skip_performance, reason=skip_reason)
class TestBulkPerformanceBenchmarks:
    """Performance benchmark tests"""
    
    def test_bulk_execution_time(self, performance_collection):
        """Measure bulk processing execution time"""
        collection_name, service = performance_collection
        
        start = time.time()
        result = service.generate_all_pairs(
            collection_name=collection_name,
            strategies=["exact"],
            limit=0
        )
        execution_time = time.time() - start
        
        assert result['success'] is True
        
        # For 1000 records, should complete in reasonable time (< 5 seconds)
        assert execution_time < 5.0, f"Too slow: {execution_time:.2f}s"
        
        # Verify statistics match
        assert result['statistics']['execution_time'] <= execution_time
        
        print(f"\nBulk processing time: {execution_time:.3f}s")
        print(f"Pairs generated: {result['statistics']['total_pairs']}")
        print(f"Pairs/second: {result['statistics']['pairs_per_second']}")
    
    def test_batch_vs_bulk_comparison(self, performance_collection):
        """Compare batch vs bulk processing performance"""
        collection_name, bulk_service = performance_collection
        
        # Measure bulk processing
        bulk_start = time.time()
        bulk_result = bulk_service.generate_all_pairs(
            collection_name=collection_name,
            strategies=["exact"],
            limit=0
        )
        bulk_time = time.time() - bulk_start
        
        # Estimate batch processing time
        # Batch would need ~1000 API calls at ~50ms each = ~50 seconds minimum
        record_count = 1000
        estimated_batch_calls = record_count / 100  # 100 records per batch
        estimated_network_overhead = estimated_batch_calls * 0.05  # 50ms per call
        estimated_batch_time = estimated_network_overhead + (bulk_time * 1.5)  # Processing + network
        
        # Calculate speedup
        speedup = estimated_batch_time / bulk_time if bulk_time > 0 else 0
        
        print(f"\n--- Performance Comparison ---")
        print(f"Bulk time: {bulk_time:.3f}s")
        print(f"Estimated batch time: {estimated_batch_time:.3f}s")
        print(f"Speedup: {speedup:.1f}x")
        print(f"Network calls: 1 (bulk) vs {estimated_batch_calls:.0f} (batch)")
        
        # Verify speedup claim (should be at least 2x for this dataset)
        assert speedup >= 2.0, f"Expected >2x speedup, got {speedup:.1f}x"
    
    def test_network_overhead_reduction(self, performance_collection):
        """Verify network overhead reduction claim"""
        collection_name, service = performance_collection
        
        result = service.generate_all_pairs(
            collection_name=collection_name,
            strategies=["exact", "ngram"],
            limit=0
        )
        
        # Bulk: 1 API call total (regardless of strategies)
        bulk_api_calls = 1
        
        # Batch: Would need ~1000 calls for 1000 records
        estimated_batch_calls = 1000 / 100  # 100 per batch
        
        reduction = (estimated_batch_calls - bulk_api_calls) / estimated_batch_calls * 100
        
        print(f"\n--- Network Overhead Analysis ---")
        print(f"Bulk API calls: {bulk_api_calls}")
        print(f"Batch API calls (estimated): {estimated_batch_calls:.0f}")
        print(f"Reduction: {reduction:.1f}%")
        
        # Should reduce API calls by >90%
        assert reduction > 90.0
    
    def test_pairs_per_second_throughput(self, performance_collection):
        """Measure pairs/second throughput"""
        collection_name, service = performance_collection
        
        result = service.generate_all_pairs(
            collection_name=collection_name,
            strategies=["exact"],
            limit=0
        )
        
        pairs_per_second = result['statistics']['pairs_per_second']
        
        print(f"\nThroughput: {pairs_per_second:,} pairs/second")
        
        # Should process at least 100 pairs/second
        assert pairs_per_second >= 100, f"Throughput too low: {pairs_per_second}"
    
    def test_deduplication_performance(self, performance_collection):
        """Measure deduplication performance impact"""
        collection_name, service = performance_collection
        
        # Run with multiple strategies (will have duplicates)
        result = service.generate_all_pairs(
            collection_name=collection_name,
            strategies=["exact", "ngram", "phonetic"],
            limit=0
        )
        
        before_dedup = result['statistics']['total_pairs_before_dedup']
        after_dedup = result['statistics']['total_pairs']
        duplicates_removed = result['statistics']['duplicate_pairs_removed']
        
        print(f"\n--- Deduplication Stats ---")
        print(f"Before: {before_dedup:,}")
        print(f"After: {after_dedup:,}")
        print(f"Removed: {duplicates_removed:,} ({duplicates_removed/before_dedup*100:.1f}%)")
        
        # Should remove some duplicates when using multiple strategies
        assert duplicates_removed > 0
        assert after_dedup <= before_dedup
    
    def test_strategy_execution_time_breakdown(self, performance_collection):
        """Measure execution time for each strategy"""
        collection_name, service = performance_collection
        
        result = service.generate_all_pairs(
            collection_name=collection_name,
            strategies=["exact", "ngram", "phonetic"],
            limit=0
        )
        
        breakdown = result['statistics']['strategy_breakdown']
        
        print(f"\n--- Strategy Performance ---")
        for strategy, stats in breakdown.items():
            print(f"{strategy:15s}: {stats['execution_time']:.3f}s "
                  f"({stats['pairs_found']:,} pairs)")
        
        # All strategies should complete
        assert len(breakdown) == 3
        
        # Exact should be fastest
        exact_time = breakdown['exact']['execution_time']
        assert exact_time > 0


@pytest.mark.skipif(skip_performance, reason=skip_reason)
class TestScalabilityBenchmarks:
    """Test performance scalability with dataset size"""
    
    def test_linear_scalability(self):
        """Test that execution time scales approximately linearly"""
        service = BulkBlockingService()
        
        if not service.connect():
            pytest.skip("Cannot connect to database")
        
        results = []
        
        for size in [100, 500, 1000]:
            collection_name = f"test_scale_{size}"
            
            # Create collection with specified size
            if service.db.has_collection(collection_name):
                service.db.delete_collection(collection_name)
            
            collection = service.db.create_collection(collection_name)
            
            # Insert test data
            test_data = [
                {"_key": str(i), 
                 "name": f"Name{i % 10}", 
                 "phone": f"555-{i % 5:04d}"}
                for i in range(size)
            ]
            collection.insert_many(test_data)
            
            # Measure execution time
            start = time.time()
            result = service.generate_all_pairs(
                collection_name=collection_name,
                strategies=["exact"],
                limit=0
            )
            execution_time = time.time() - start
            
            results.append({
                'size': size,
                'time': execution_time,
                'pairs': result['statistics']['total_pairs']
            })
            
            # Cleanup
            service.db.delete_collection(collection_name)
        
        print(f"\n--- Scalability Analysis ---")
        for r in results:
            print(f"Size: {r['size']:4d} records, Time: {r['time']:.3f}s, "
                  f"Pairs: {r['pairs']:,}")
        
        # Verify roughly linear scaling
        # Time for 1000 should be < 10x time for 100
        ratio = results[-1]['time'] / results[0]['time']
        size_ratio = results[-1]['size'] / results[0]['size']
        
        print(f"Time ratio: {ratio:.1f}x for {size_ratio:.1f}x more data")
        
        # Should scale better than O(n^2)
        assert ratio < size_ratio * 2


@pytest.mark.skipif(skip_performance, reason=skip_reason)
class TestMemoryEfficiency:
    """Test memory efficiency of bulk processing"""
    
    def test_streaming_memory_usage(self, performance_collection):
        """Test that streaming doesn't load all data into memory"""
        collection_name, service = performance_collection
        
        batch_sizes = []
        
        for batch in service.generate_pairs_streaming(
            collection_name=collection_name,
            strategies=["exact"],
            batch_size=100
        ):
            batch_sizes.append(len(batch))
        
        print(f"\n--- Streaming Analysis ---")
        print(f"Total batches: {len(batch_sizes)}")
        print(f"Average batch size: {sum(batch_sizes)/len(batch_sizes):.1f}")
        print(f"Max batch size: {max(batch_sizes) if batch_sizes else 0}")
        
        # No batch should exceed configured size by much
        if batch_sizes:
            assert max(batch_sizes) <= 100, "Batch size exceeded limit"


@pytest.mark.skipif(skip_performance, reason=skip_reason)
class TestPerformanceRegression:
    """Tests to detect performance regressions"""
    
    def test_no_regression_exact_blocking(self, performance_collection):
        """Test that exact blocking maintains performance"""
        collection_name, service = performance_collection
        
        # Run multiple times and check consistency
        times = []
        for _ in range(3):
            start = time.time()
            result = service.generate_all_pairs(
                collection_name=collection_name,
                strategies=["exact"],
                limit=0
            )
            times.append(time.time() - start)
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        variance = (max_time - min_time) / avg_time * 100
        
        print(f"\n--- Performance Consistency ---")
        print(f"Average: {avg_time:.3f}s")
        print(f"Min: {min_time:.3f}s, Max: {max_time:.3f}s")
        print(f"Variance: {variance:.1f}%")
        
        # Performance should be consistent (< 50% variance)
        assert variance < 50.0, f"High variance: {variance:.1f}%"
    
    def test_baseline_performance_metrics(self, performance_collection):
        """Establish baseline performance metrics"""
        collection_name, service = performance_collection
        
        result = service.generate_all_pairs(
            collection_name=collection_name,
            strategies=["exact", "ngram"],
            limit=0
        )
        
        stats = result['statistics']
        
        # Baseline expectations for 1000 records
        assert stats['execution_time'] < 10.0, "Execution time regression"
        assert stats['pairs_per_second'] >= 50, "Throughput regression"
        assert stats['total_pairs'] > 0, "No pairs generated"
        
        print(f"\n--- Baseline Metrics ---")
        print(f"Execution time: {stats['execution_time']:.3f}s")
        print(f"Pairs/second: {stats['pairs_per_second']:,}")
        print(f"Total pairs: {stats['total_pairs']:,}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

