#!/usr/bin/env python3
"""
Performance Benchmarking: Python vs Foxx Services

Comprehensive performance comparison between Python fallback and Foxx native implementations.
Tests similarity computation, blocking operations, and clustering algorithms.
"""

import sys
import time
import json
import statistics
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from entity_resolution.utils.config import Config, get_config
from entity_resolution.utils.logging import get_logger
from entity_resolution.services.similarity_service import SimilarityService
from entity_resolution.services.blocking_service import BlockingService
from entity_resolution.services.clustering_service import ClusteringService

logger = get_logger(__name__)

@dataclass
class BenchmarkResult:
    """Store benchmark results for comparison"""
    operation: str
    method: str  # 'python' or 'foxx'
    records_processed: int
    total_time: float
    throughput: float
    memory_usage: float = 0.0
    success_rate: float = 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'operation': self.operation,
            'method': self.method,
            'records_processed': self.records_processed,
            'total_time_seconds': round(self.total_time, 4),
            'throughput_per_second': round(self.throughput, 2),
            'memory_usage_mb': round(self.memory_usage, 2),
            'success_rate_percent': round(self.success_rate, 2)
        }

class PerformanceBenchmark:
    """Performance benchmarking suite for entity resolution services"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize services
        self.similarity_service = SimilarityService(config)
        self.blocking_service = BlockingService(config)
        self.clustering_service = ClusteringService(config)
        
        # Test data
        self.test_documents = self._generate_test_documents()
        self.test_pairs = self._generate_test_pairs()
        
    def _generate_test_documents(self) -> List[Dict[str, Any]]:
        """Generate test documents for benchmarking"""
        documents = []
        
        # Base patterns for realistic data generation
        first_names = ["John", "Jane", "Michael", "Sarah", "David", "Lisa", "Robert", "Mary"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
        domains = ["gmail.com", "yahoo.com", "outlook.com", "company.com"]
        
        for i in range(100):
            # Create base record
            first_name = first_names[i % len(first_names)]
            last_name = last_names[i % len(last_names)]
            
            doc = {
                "_id": f"customer_{i:04d}",
                "first_name": first_name,
                "last_name": last_name,
                "email": f"{first_name.lower()}.{last_name.lower()}@{domains[i % len(domains)]}",
                "phone": f"555-{i:04d}",
                "address": f"{100 + i} Main St",
                "city": "Springfield",
                "state": "IL",
                "zip_code": f"{60000 + (i % 100):05d}",
                "company": f"Company {chr(65 + (i % 26))}"
            }
            
            documents.append(doc)
            
            # Create variations for similarity testing
            if i % 10 == 0:  # Every 10th record gets variations
                # Typo variation
                typo_doc = doc.copy()
                typo_doc["_id"] = f"customer_{i:04d}_typo"
                typo_doc["first_name"] = first_name[:-1] + "n"  # Change last letter
                documents.append(typo_doc)
                
                # Format variation
                format_doc = doc.copy()
                format_doc["_id"] = f"customer_{i:04d}_format"
                format_doc["phone"] = f"({format_doc['phone'][:3]}) {format_doc['phone'][4:]}"
                documents.append(format_doc)
        
        return documents
    
    def _generate_test_pairs(self) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Generate document pairs for similarity testing"""
        pairs = []
        docs = self.test_documents
        
        # Generate pairs with different similarity levels
        for i in range(0, min(50, len(docs)), 2):
            if i + 1 < len(docs):
                pairs.append((docs[i], docs[i + 1]))
        
        return pairs
    
    def benchmark_similarity_service(self) -> List[BenchmarkResult]:
        """Benchmark similarity computation performance"""
        results = []
        
        # Force Python mode for baseline
        self.similarity_service.foxx_available = False
        
        # Benchmark Python implementation
        start_time = time.time()
        python_results = []
        
        for doc_a, doc_b in self.test_pairs:
            try:
                result = self.similarity_service.compute_similarity(doc_a, doc_b)
                python_results.append(result)
            except Exception as e:
                self.logger.warning(f"Python similarity failed: {e}")
        
        python_time = time.time() - start_time
        python_throughput = len(self.test_pairs) / python_time if python_time > 0 else 0
        
        results.append(BenchmarkResult(
            operation="similarity_computation",
            method="python",
            records_processed=len(self.test_pairs),
            total_time=python_time,
            throughput=python_throughput,
            success_rate=(len(python_results) / len(self.test_pairs)) * 100
        ))
        
        # Test Foxx availability and benchmark if available
        if self.similarity_service.connect() and self.similarity_service.foxx_available:
            start_time = time.time()
            foxx_results = []
            
            for doc_a, doc_b in self.test_pairs:
                try:
                    result = self.similarity_service.compute_similarity(doc_a, doc_b)
                    foxx_results.append(result)
                except Exception as e:
                    self.logger.warning(f"Foxx similarity failed: {e}")
            
            foxx_time = time.time() - start_time
            foxx_throughput = len(self.test_pairs) / foxx_time if foxx_time > 0 else 0
            
            results.append(BenchmarkResult(
                operation="similarity_computation",
                method="foxx",
                records_processed=len(self.test_pairs),
                total_time=foxx_time,
                throughput=foxx_throughput,
                success_rate=(len(foxx_results) / len(self.test_pairs)) * 100
            ))
        else:
            self.logger.warning("Foxx similarity service not available for benchmarking")
        
        return results
    
    def benchmark_blocking_service(self) -> List[BenchmarkResult]:
        """Benchmark blocking performance"""
        results = []
        
        # Force Python mode for baseline
        self.blocking_service.foxx_available = False
        
        # Benchmark Python implementation
        start_time = time.time()
        python_candidates = 0
        
        for doc in self.test_documents[:20]:  # Test with subset
            try:
                result = self.blocking_service.generate_candidates(
                    collection="customers",
                    target_record_id=doc["_id"],
                    strategies=["exact", "ngram"],
                    limit=10
                )
                if result.get("success"):
                    python_candidates += len(result.get("candidates", []))
            except Exception as e:
                self.logger.warning(f"Python blocking failed: {e}")
        
        python_time = time.time() - start_time
        python_throughput = 20 / python_time if python_time > 0 else 0
        
        results.append(BenchmarkResult(
            operation="blocking_candidates",
            method="python",
            records_processed=20,
            total_time=python_time,
            throughput=python_throughput
        ))
        
        # Test Foxx availability
        if self.blocking_service.connect() and self.blocking_service.foxx_available:
            start_time = time.time()
            foxx_candidates = 0
            
            for doc in self.test_documents[:20]:
                try:
                    result = self.blocking_service.generate_candidates(
                        collection="customers",
                        target_record_id=doc["_id"],
                        strategies=["exact", "ngram"],
                        limit=10
                    )
                    if result.get("success"):
                        foxx_candidates += len(result.get("candidates", []))
                except Exception as e:
                    self.logger.warning(f"Foxx blocking failed: {e}")
            
            foxx_time = time.time() - start_time
            foxx_throughput = 20 / foxx_time if foxx_time > 0 else 0
            
            results.append(BenchmarkResult(
                operation="blocking_candidates",
                method="foxx",
                records_processed=20,
                total_time=foxx_time,
                throughput=foxx_throughput
            ))
        else:
            self.logger.warning("Foxx blocking service not available for benchmarking")
        
        return results
    
    def benchmark_clustering_service(self) -> List[BenchmarkResult]:
        """Benchmark clustering performance"""
        results = []
        
        # Generate synthetic similarity data for clustering
        scored_pairs = []
        for i, (doc_a, doc_b) in enumerate(self.test_pairs[:30]):
            scored_pairs.append({
                "doc_a_id": doc_a["_id"],
                "doc_b_id": doc_b["_id"],
                "similarity_score": 0.7 + (i % 3) * 0.1,  # Vary scores
                "is_match": True
            })
        
        # Force Python mode for baseline
        self.clustering_service.foxx_available = False
        
        # Benchmark Python implementation
        start_time = time.time()
        try:
            python_result = self.clustering_service.cluster_entities(
                scored_pairs=scored_pairs,
                min_similarity=0.7
            )
            python_time = time.time() - start_time
            python_throughput = len(scored_pairs) / python_time if python_time > 0 else 0
            
            results.append(BenchmarkResult(
                operation="entity_clustering",
                method="python",
                records_processed=len(scored_pairs),
                total_time=python_time,
                throughput=python_throughput,
                success_rate=100.0 if python_result.get("success") else 0.0
            ))
        except Exception as e:
            self.logger.warning(f"Python clustering failed: {e}")
        
        # Test Foxx availability
        if self.clustering_service.connect() and self.clustering_service.foxx_available:
            start_time = time.time()
            try:
                foxx_result = self.clustering_service.cluster_entities(
                    scored_pairs=scored_pairs,
                    min_similarity=0.7
                )
                foxx_time = time.time() - start_time
                foxx_throughput = len(scored_pairs) / foxx_time if foxx_time > 0 else 0
                
                results.append(BenchmarkResult(
                    operation="entity_clustering",
                    method="foxx",
                    records_processed=len(scored_pairs),
                    total_time=foxx_time,
                    throughput=foxx_throughput,
                    success_rate=100.0 if foxx_result.get("success") else 0.0
                ))
            except Exception as e:
                self.logger.warning(f"Foxx clustering failed: {e}")
        else:
            self.logger.warning("Foxx clustering service not available for benchmarking")
        
        return results
    
    def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run complete performance benchmark suite"""
        self.logger.info("Starting comprehensive performance benchmark")
        
        all_results = []
        
        # Benchmark each service
        self.logger.info("Benchmarking similarity service...")
        all_results.extend(self.benchmark_similarity_service())
        
        self.logger.info("Benchmarking blocking service...")
        all_results.extend(self.benchmark_blocking_service())
        
        self.logger.info("Benchmarking clustering service...")
        all_results.extend(self.benchmark_clustering_service())
        
        # Calculate performance improvements
        improvements = self._calculate_improvements(all_results)
        
        # Generate report
        report = {
            "benchmark_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "test_configuration": {
                "test_documents": len(self.test_documents),
                "test_pairs": len(self.test_pairs),
                "foxx_enabled": any(r.method == "foxx" for r in all_results)
            },
            "results": [r.to_dict() for r in all_results],
            "performance_improvements": improvements,
            "summary": self._generate_summary(all_results, improvements)
        }
        
        return report
    
    def _calculate_improvements(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        """Calculate performance improvements between Python and Foxx"""
        improvements = {}
        
        # Group results by operation
        by_operation = {}
        for result in results:
            if result.operation not in by_operation:
                by_operation[result.operation] = {}
            by_operation[result.operation][result.method] = result
        
        # Calculate improvements
        for operation, methods in by_operation.items():
            if "python" in methods and "foxx" in methods:
                python_result = methods["python"]
                foxx_result = methods["foxx"]
                
                throughput_improvement = (
                    foxx_result.throughput / python_result.throughput 
                    if python_result.throughput > 0 else 0
                )
                
                time_improvement = (
                    python_result.total_time / foxx_result.total_time
                    if foxx_result.total_time > 0 else 0
                )
                
                improvements[operation] = {
                    "throughput_multiplier": round(throughput_improvement, 2),
                    "time_speedup": round(time_improvement, 2),
                    "python_throughput": round(python_result.throughput, 2),
                    "foxx_throughput": round(foxx_result.throughput, 2)
                }
        
        return improvements
    
    def _generate_summary(self, results: List[BenchmarkResult], improvements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate performance summary"""
        python_results = [r for r in results if r.method == "python"]
        foxx_results = [r for r in results if r.method == "foxx"]
        
        summary = {
            "operations_tested": len(set(r.operation for r in results)),
            "python_avg_throughput": round(statistics.mean([r.throughput for r in python_results]), 2) if python_results else 0,
            "foxx_avg_throughput": round(statistics.mean([r.throughput for r in foxx_results]), 2) if foxx_results else 0,
            "overall_improvement": 0,
            "foxx_availability": len(foxx_results) > 0
        }
        
        if summary["python_avg_throughput"] > 0 and summary["foxx_avg_throughput"] > 0:
            summary["overall_improvement"] = round(
                summary["foxx_avg_throughput"] / summary["python_avg_throughput"], 2
            )
        
        return summary

def main():
    """Main benchmarking function"""
    logger.info("Entity Resolution Performance Benchmark")
    logger.info("=" * 50)
    
    config = get_config()
    benchmark = PerformanceBenchmark(config)
    
    # Run comprehensive benchmark
    report = benchmark.run_comprehensive_benchmark()
    
    # Save report
    report_path = Path("reports/performance_benchmark.json")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Display results
    logger.info("PERFORMANCE BENCHMARK RESULTS")
    logger.info("=" * 40)
    
    for operation, improvement in report["performance_improvements"].items():
        logger.info(f"{operation}:")
        logger.info(f"  Python: {improvement['python_throughput']:.2f} ops/sec")
        logger.info(f"  Foxx: {improvement['foxx_throughput']:.2f} ops/sec")
        logger.info(f"  Improvement: {improvement['throughput_multiplier']:.2f}x faster")
        logger.info("")
    
    summary = report["summary"]
    logger.info(f"OVERALL SUMMARY:")
    logger.info(f"  Operations tested: {summary['operations_tested']}")
    logger.info(f"  Foxx services available: {summary['foxx_availability']}")
    logger.info(f"  Average improvement: {summary['overall_improvement']:.2f}x")
    logger.info(f"  Report saved: {report_path}")
    
    return report

if __name__ == "__main__":
    main()
