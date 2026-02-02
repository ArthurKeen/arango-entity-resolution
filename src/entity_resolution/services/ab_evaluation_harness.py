"""
A/B Evaluation Harness for Blocking Strategies

Compares baseline (traditional) blocking vs hybrid (traditional + embeddings) blocking.
Outputs evaluation metrics in JSON and CSV formats.

Metrics Calculated:
- Precision, Recall, F1 Score
- Reduction Ratio (comparisons avoided)
- Pairs Completeness (recall at blocking stage)
- Candidate Generation Time
- Throughput (pairs per second)
"""

import logging
import json
import csv
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from ..utils.database import DatabaseManager
from .embedding_service import EmbeddingService
from .tuple_embedding_serializer import TupleEmbeddingSerializer


@dataclass
class BlockingResult:
    """Result from a blocking strategy run."""
    strategy_name: str
    candidate_pairs: List[Dict[str, Any]]
    execution_time: float
    total_comparisons: int
    records_processed: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for a blocking strategy."""
    strategy_name: str
    precision: float
    recall: float
    f1_score: float
    reduction_ratio: float  # Percentage of comparisons avoided
    pairs_completeness: float  # Recall at blocking stage
    true_positives: int
    false_positives: int
    false_negatives: int
    total_candidates: int
    total_true_matches: int
    execution_time: float
    throughput: float  # Pairs per second
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ABEvaluationHarness:
    """
    A/B evaluation harness for comparing blocking strategies.
    
    Compares baseline (traditional) blocking against hybrid (traditional + embeddings)
    blocking strategies and outputs comprehensive metrics.
    
    Example:
        >>> harness = ABEvaluationHarness(
        ...     db_manager=db_manager,
        ...     collection_name="customers",
        ...     ground_truth=ground_truth_pairs
        ... )
        >>> results = harness.evaluate(
        ...     baseline_strategy=baseline_blocking,
        ...     hybrid_strategy=hybrid_blocking
        ... )
        >>> harness.save_results(results, output_dir="./evaluation_results")
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        collection_name: str,
        ground_truth: List[Dict[str, Any]],
        embedding_service: Optional[EmbeddingService] = None,
        serializer: Optional[TupleEmbeddingSerializer] = None,
        database_name: Optional[str] = None
    ):
        """
        Initialize A/B evaluation harness.
        
        Args:
            db_manager: DatabaseManager instance for database access
            collection_name: Name of the collection to evaluate
            ground_truth: List of ground truth pairs with 'record_a_id', 'record_b_id', 'is_match'
            embedding_service: Optional EmbeddingService for hybrid blocking
            serializer: Optional TupleEmbeddingSerializer for tuple serialization
            database_name: Optional database name
        """
        self.db_manager = db_manager
        self.collection_name = collection_name
        self.ground_truth = ground_truth
        self.embedding_service = embedding_service
        self.serializer = serializer
        self.database_name = database_name
        
        self.logger = logging.getLogger(__name__)
        
        # Validate ground truth format
        self._validate_ground_truth()
        
        # Precompute ground truth sets for fast lookup
        self.true_match_pairs = {
            self._canonical_pair_id(pair['record_a_id'], pair['record_b_id'])
            for pair in self.ground_truth
            if pair.get('is_match', False)
        }
        self.total_true_matches = len(self.true_match_pairs)
        
        self.logger.info(
            f"Initialized A/B Evaluation Harness: "
            f"collection={collection_name}, "
            f"ground_truth_pairs={len(self.ground_truth)}, "
            f"true_matches={self.total_true_matches}"
        )
    
    def _validate_ground_truth(self):
        """Validate ground truth format."""
        required_fields = ['record_a_id', 'record_b_id', 'is_match']
        for i, pair in enumerate(self.ground_truth):
            for field in required_fields:
                if field not in pair:
                    raise ValueError(
                        f"Ground truth pair {i} missing required field: {field}"
                    )
            if not isinstance(pair['is_match'], bool):
                raise ValueError(
                    f"Ground truth pair {i} has invalid 'is_match' value (must be bool)"
                )
    
    def _canonical_pair_id(self, id_a: str, id_b: str) -> str:
        """Create canonical pair ID (smaller ID first)."""
        return f"{min(id_a, id_b)}|{max(id_a, id_b)}"
    
    def _is_true_match(self, id_a: str, id_b: str) -> bool:
        """Check if pair is a true match according to ground truth."""
        pair_id = self._canonical_pair_id(id_a, id_b)
        return pair_id in self.true_match_pairs
    
    def evaluate_blocking_strategy(
        self,
        strategy_name: str,
        blocking_function,
        *args,
        **kwargs
    ) -> EvaluationMetrics:
        """
        Evaluate a single blocking strategy.
        
        Args:
            strategy_name: Name of the strategy (e.g., "baseline", "hybrid")
            blocking_function: Function that generates candidate pairs.
                Must return dict with 'candidate_pairs' list and 'execution_time' float.
                Each pair should have 'record_a_id' and 'record_b_id'.
            *args: Additional positional arguments for blocking_function
            **kwargs: Additional keyword arguments for blocking_function
        
        Returns:
            EvaluationMetrics object with computed metrics
        """
        self.logger.info(f"Evaluating strategy: {strategy_name}")
        
        start_time = time.time()
        
        # Run blocking strategy
        try:
            result = blocking_function(*args, **kwargs)
            
            # Handle different return formats
            if isinstance(result, dict):
                candidate_pairs = result.get('candidate_pairs', result.get('candidates', []))
                execution_time = result.get('execution_time', time.time() - start_time)
            elif isinstance(result, list):
                candidate_pairs = result
                execution_time = time.time() - start_time
            else:
                raise ValueError(f"Unexpected blocking function return type: {type(result)}")
            
        except Exception as e:
            self.logger.error(f"Blocking strategy '{strategy_name}' failed: {e}")
            raise
        
        # Calculate metrics
        metrics = self._calculate_metrics(
            strategy_name=strategy_name,
            candidate_pairs=candidate_pairs,
            execution_time=execution_time
        )
        
        self.logger.info(
            f"Strategy '{strategy_name}' evaluation complete: "
            f"precision={metrics.precision:.3f}, "
            f"recall={metrics.recall:.3f}, "
            f"f1={metrics.f1_score:.3f}"
        )
        
        return metrics
    
    def _calculate_metrics(
        self,
        strategy_name: str,
        candidate_pairs: List[Dict[str, Any]],
        execution_time: float
    ) -> EvaluationMetrics:
        """
        Calculate evaluation metrics from candidate pairs.
        
        Args:
            strategy_name: Name of the strategy
            candidate_pairs: List of candidate pairs
            execution_time: Execution time in seconds
        
        Returns:
            EvaluationMetrics object
        """
        # Extract pair IDs
        pair_ids = set()
        for pair in candidate_pairs:
            id_a = pair.get('record_a_id') or pair.get('_from', '').split('/')[-1]
            id_b = pair.get('record_b_id') or pair.get('_to', '').split('/')[-1]
            if id_a and id_b:
                pair_ids.add(self._canonical_pair_id(id_a, id_b))
        
        # Count true positives, false positives, false negatives
        true_positives = sum(1 for pair_id in pair_ids if pair_id in self.true_match_pairs)
        false_positives = len(pair_ids) - true_positives
        false_negatives = self.total_true_matches - true_positives
        
        # Calculate precision, recall, F1
        precision = true_positives / len(pair_ids) if len(pair_ids) > 0 else 0.0
        recall = true_positives / self.total_true_matches if self.total_true_matches > 0 else 0.0
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )
        
        # Calculate reduction ratio (comparisons avoided)
        # Total possible comparisons: n * (n-1) / 2
        db = self.db_manager.get_database(self.database_name)
        collection = db.collection(self.collection_name)
        total_records = collection.count()
        total_possible_comparisons = (total_records * (total_records - 1)) // 2
        reduction_ratio = (
            (total_possible_comparisons - len(pair_ids)) / total_possible_comparisons * 100
            if total_possible_comparisons > 0 else 0.0
        )
        
        # Pairs completeness (same as recall for blocking stage)
        pairs_completeness = recall
        
        # Throughput
        throughput = len(pair_ids) / execution_time if execution_time > 0 else 0.0
        
        return EvaluationMetrics(
            strategy_name=strategy_name,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            reduction_ratio=reduction_ratio,
            pairs_completeness=pairs_completeness,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            total_candidates=len(pair_ids),
            total_true_matches=self.total_true_matches,
            execution_time=execution_time,
            throughput=throughput
        )
    
    def evaluate(
        self,
        baseline_strategy,
        hybrid_strategy,
        baseline_args: Optional[Tuple] = None,
        baseline_kwargs: Optional[Dict] = None,
        hybrid_args: Optional[Tuple] = None,
        hybrid_kwargs: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Run A/B evaluation comparing baseline vs hybrid strategies.
        
        Args:
            baseline_strategy: Blocking function for baseline (traditional) blocking
            hybrid_strategy: Blocking function for hybrid (traditional + embeddings) blocking
            baseline_args: Optional positional arguments for baseline_strategy
            baseline_kwargs: Optional keyword arguments for baseline_strategy
            hybrid_args: Optional positional arguments for hybrid_strategy
            hybrid_kwargs: Optional keyword arguments for hybrid_strategy
        
        Returns:
            Dictionary with evaluation results for both strategies and comparison
        """
        baseline_args = baseline_args or ()
        baseline_kwargs = baseline_kwargs or {}
        hybrid_args = hybrid_args or ()
        hybrid_kwargs = hybrid_kwargs or {}
        
        # Evaluate baseline
        baseline_metrics = self.evaluate_blocking_strategy(
            "baseline",
            baseline_strategy,
            *baseline_args,
            **baseline_kwargs
        )
        
        # Evaluate hybrid
        hybrid_metrics = self.evaluate_blocking_strategy(
            "hybrid",
            hybrid_strategy,
            *hybrid_args,
            **hybrid_kwargs
        )
        
        # Calculate improvements
        improvements = {
            'precision_delta': hybrid_metrics.precision - baseline_metrics.precision,
            'recall_delta': hybrid_metrics.recall - baseline_metrics.recall,
            'f1_delta': hybrid_metrics.f1_score - baseline_metrics.f1_score,
            'reduction_ratio_delta': (
                hybrid_metrics.reduction_ratio - baseline_metrics.reduction_ratio
            ),
            'throughput_delta': hybrid_metrics.throughput - baseline_metrics.throughput,
            'execution_time_delta': (
                hybrid_metrics.execution_time - baseline_metrics.execution_time
            )
        }
        
        # Calculate percentage improvements
        def pct_change(new_val: float, old_val: float) -> Optional[float]:
            if old_val == 0:
                return None
            return ((new_val - old_val) / old_val) * 100
        
        improvements['precision_pct_change'] = pct_change(
            hybrid_metrics.precision, baseline_metrics.precision
        )
        improvements['recall_pct_change'] = pct_change(
            hybrid_metrics.recall, baseline_metrics.recall
        )
        improvements['f1_pct_change'] = pct_change(
            hybrid_metrics.f1_score, baseline_metrics.f1_score
        )
        
        results = {
            'metadata': {
                'collection': self.collection_name,
                'database': self.database_name,
                'evaluation_date': datetime.utcnow().isoformat(),
                'ground_truth_pairs': len(self.ground_truth),
                'true_matches': self.total_true_matches
            },
            'baseline': baseline_metrics.to_dict(),
            'hybrid': hybrid_metrics.to_dict(),
            'improvements': improvements
        }
        
        return results
    
    def save_results(
        self,
        results: Dict[str, Any],
        output_dir: str,
        filename_prefix: str = "ab_evaluation"
    ) -> Dict[str, str]:
        """
        Save evaluation results to JSON and CSV files.
        
        Args:
            results: Results dictionary from evaluate() method
            output_dir: Directory to save output files
            filename_prefix: Prefix for output filenames
        
        Returns:
            Dictionary with paths to saved files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON
        json_path = output_path / f"{filename_prefix}_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save CSV (comparison table)
        csv_path = output_path / f"{filename_prefix}_{timestamp}.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'Metric', 'Baseline', 'Hybrid', 'Delta', 'Percent Change'
            ])
            
            # Write metrics
            baseline = results['baseline']
            hybrid = results['hybrid']
            improvements = results['improvements']
            
            metrics_to_write = [
                ('Precision', baseline['precision'], hybrid['precision'],
                 improvements['precision_delta'], improvements['precision_pct_change']),
                ('Recall', baseline['recall'], hybrid['recall'],
                 improvements['recall_delta'], improvements['recall_pct_change']),
                ('F1 Score', baseline['f1_score'], hybrid['f1_score'],
                 improvements['f1_delta'], improvements['f1_pct_change']),
                ('Reduction Ratio (%)', baseline['reduction_ratio'], hybrid['reduction_ratio'],
                 improvements['reduction_ratio_delta'], None),
                ('Throughput (pairs/sec)', baseline['throughput'], hybrid['throughput'],
                 improvements['throughput_delta'], None),
                ('Execution Time (sec)', baseline['execution_time'], hybrid['execution_time'],
                 improvements['execution_time_delta'], None),
                ('True Positives', baseline['true_positives'], hybrid['true_positives'],
                 hybrid['true_positives'] - baseline['true_positives'], None),
                ('False Positives', baseline['false_positives'], hybrid['false_positives'],
                 hybrid['false_positives'] - baseline['false_positives'], None),
                ('False Negatives', baseline['false_negatives'], hybrid['false_negatives'],
                 hybrid['false_negatives'] - baseline['false_negatives'], None),
            ]
            
            for row in metrics_to_write:
                metric_name, baseline_val, hybrid_val, delta, pct_change = row
                pct_str = f"{pct_change:.2f}%" if pct_change is not None else "N/A"
                writer.writerow([
                    metric_name,
                    f"{baseline_val:.4f}" if isinstance(baseline_val, float) else baseline_val,
                    f"{hybrid_val:.4f}" if isinstance(hybrid_val, float) else hybrid_val,
                    f"{delta:.4f}" if isinstance(delta, float) else delta,
                    pct_str
                ])
        
        self.logger.info(f"Saved evaluation results: {json_path}, {csv_path}")
        
        return {
            'json': str(json_path),
            'csv': str(csv_path)
        }
