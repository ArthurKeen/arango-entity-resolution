"""
Tests for ABEvaluationHarness

Tests evaluation metrics calculation, A/B comparison, and output formats.
"""

import pytest
import json
import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

from entity_resolution.services.ab_evaluation_harness import (
    ABEvaluationHarness,
    EvaluationMetrics,
    BlockingResult
)
from entity_resolution.utils.database import DatabaseManager


class TestEvaluationMetrics:
    """Test evaluation metrics calculation."""
    
    def test_metrics_calculation_perfect_match(self):
        """Test metrics when all predictions are correct."""
        harness = self._create_harness()
        
        # All candidates are true matches
        candidate_pairs = [
            {"record_a_id": "1", "record_b_id": "2"},
            {"record_a_id": "3", "record_b_id": "4"}
        ]
        
        metrics = harness._calculate_metrics(
            "test_strategy",
            candidate_pairs,
            execution_time=1.0
        )
        
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0
        assert metrics.true_positives == 2
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 0
    
    def test_metrics_calculation_with_false_positives(self):
        """Test metrics with false positives."""
        harness = self._create_harness()
        
        # One true match, one false positive
        candidate_pairs = [
            {"record_a_id": "1", "record_b_id": "2"},  # True match
            {"record_a_id": "5", "record_b_id": "6"}   # False positive
        ]
        
        metrics = harness._calculate_metrics(
            "test_strategy",
            candidate_pairs,
            execution_time=1.0
        )
        
        assert metrics.precision == 0.5  # 1 true positive / 2 total
        assert metrics.recall == 0.5     # 1 true positive / 2 true matches
        assert metrics.f1_score == pytest.approx(0.5)
        assert metrics.true_positives == 1
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 1
    
    def test_metrics_calculation_with_false_negatives(self):
        """Test metrics with false negatives."""
        harness = self._create_harness()
        
        # Only one candidate, but there are two true matches
        candidate_pairs = [
            {"record_a_id": "1", "record_b_id": "2"}  # True match
        ]
        
        metrics = harness._calculate_metrics(
            "test_strategy",
            candidate_pairs,
            execution_time=1.0
        )
        
        assert metrics.precision == 1.0
        assert metrics.recall == 0.5  # 1 found / 2 true matches
        assert metrics.f1_score == pytest.approx(2/3)
        assert metrics.true_positives == 1
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 1
    
    def test_metrics_zero_candidates(self):
        """Test metrics when no candidates are generated."""
        harness = self._create_harness()
        
        candidate_pairs = []
        
        metrics = harness._calculate_metrics(
            "test_strategy",
            candidate_pairs,
            execution_time=1.0
        )
        
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0
        assert metrics.true_positives == 0
        assert metrics.false_positives == 0
        assert metrics.false_negatives == 2  # All true matches missed
    
    def test_throughput_calculation(self):
        """Test throughput calculation."""
        harness = self._create_harness()
        
        candidate_pairs = [
            {"record_a_id": "1", "record_b_id": "2"},
            {"record_a_id": "3", "record_b_id": "4"}
        ]
        
        metrics = harness._calculate_metrics(
            "test_strategy",
            candidate_pairs,
            execution_time=0.5  # 2 pairs in 0.5 seconds = 4 pairs/sec
        )
        
        assert metrics.throughput == pytest.approx(4.0)
    
    def _create_harness(self):
        """Create a test harness with mock ground truth."""
        db_manager = Mock(spec=DatabaseManager)
        db = Mock()
        collection = Mock()
        collection.count.return_value = 100  # 100 records
        db.collection.return_value = collection
        db_manager.get_database.return_value = db
        
        ground_truth = [
            {"record_a_id": "1", "record_b_id": "2", "is_match": True},
            {"record_a_id": "3", "record_b_id": "4", "is_match": True},
            {"record_a_id": "5", "record_b_id": "6", "is_match": False}
        ]
        
        return ABEvaluationHarness(
            db_manager=db_manager,
            collection_name="test_collection",
            ground_truth=ground_truth
        )


class TestABEvaluationHarness:
    """Test A/B evaluation harness."""
    
    def test_ground_truth_validation(self):
        """Test ground truth format validation."""
        db_manager = Mock(spec=DatabaseManager)
        
        # Missing required field
        invalid_gt = [
            {"record_a_id": "1", "record_b_id": "2"}  # Missing "is_match"
        ]
        
        with pytest.raises(ValueError, match="missing required field"):
            ABEvaluationHarness(
                db_manager=db_manager,
                collection_name="test",
                ground_truth=invalid_gt
            )
        
        # Invalid is_match type
        invalid_gt2 = [
            {"record_a_id": "1", "record_b_id": "2", "is_match": "yes"}  # Should be bool
        ]
        
        with pytest.raises(ValueError, match="invalid 'is_match' value"):
            ABEvaluationHarness(
                db_manager=db_manager,
                collection_name="test",
                ground_truth=invalid_gt2
            )
    
    def test_canonical_pair_id(self):
        """Test canonical pair ID generation."""
        harness = self._create_harness()
        
        # Should be same regardless of order
        id1 = harness._canonical_pair_id("1", "2")
        id2 = harness._canonical_pair_id("2", "1")
        
        assert id1 == id2
        assert id1 == "1|2"
    
    def test_is_true_match(self):
        """Test true match detection."""
        harness = self._create_harness()
        
        assert harness._is_true_match("1", "2") is True
        assert harness._is_true_match("3", "4") is True
        assert harness._is_true_match("5", "6") is False
        assert harness._is_true_match("1", "3") is False
    
    def test_evaluate_blocking_strategy(self):
        """Test evaluating a single blocking strategy."""
        harness = self._create_harness()
        
        def mock_blocking():
            return {
                "candidate_pairs": [
                    {"record_a_id": "1", "record_b_id": "2"}
                ],
                "execution_time": 0.5
            }
        
        metrics = harness.evaluate_blocking_strategy("test", mock_blocking)
        
        assert isinstance(metrics, EvaluationMetrics)
        assert metrics.strategy_name == "test"
        assert metrics.execution_time == 0.5
    
    def test_evaluate_ab_comparison(self):
        """Test A/B evaluation comparing two strategies."""
        harness = self._create_harness()
        
        def baseline_blocking():
            return {
                "candidate_pairs": [
                    {"record_a_id": "1", "record_b_id": "2"}
                ],
                "execution_time": 1.0
            }
        
        def hybrid_blocking():
            return {
                "candidate_pairs": [
                    {"record_a_id": "1", "record_b_id": "2"},
                    {"record_a_id": "3", "record_b_id": "4"}
                ],
                "execution_time": 1.5
            }
        
        results = harness.evaluate(
            baseline_strategy=baseline_blocking,
            hybrid_strategy=hybrid_blocking
        )
        
        assert "baseline" in results
        assert "hybrid" in results
        assert "improvements" in results
        assert "metadata" in results
        
        # Hybrid should have better recall (found both true matches)
        assert results["hybrid"]["recall"] > results["baseline"]["recall"]
        assert results["improvements"]["recall_delta"] > 0
    
    def test_save_results_json(self):
        """Test saving results to JSON file."""
        harness = self._create_harness()
        
        results = {
            "metadata": {"collection": "test"},
            "baseline": {
                "precision": 0.5,
                "recall": 0.5,
                "f1_score": 0.5,
                "reduction_ratio": 95.0,
                "throughput": 100.0,
                "execution_time": 1.0,
                "true_positives": 1,
                "false_positives": 1,
                "false_negatives": 1
            },
            "hybrid": {
                "precision": 0.6,
                "recall": 0.7,
                "f1_score": 0.65,
                "reduction_ratio": 96.0,
                "throughput": 120.0,
                "execution_time": 1.2,
                "true_positives": 2,
                "false_positives": 1,
                "false_negatives": 0
            },
            "improvements": {
                "precision_delta": 0.1,
                "recall_delta": 0.2,
                "f1_delta": 0.15,
                "precision_pct_change": 20.0,
                "recall_pct_change": 40.0,
                "f1_pct_change": 30.0,
                "reduction_ratio_delta": 1.0,
                "throughput_delta": 20.0,
                "execution_time_delta": 0.2
            }
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_files = harness.save_results(results, tmpdir)
            
            assert "json" in saved_files
            json_path = Path(saved_files["json"])
            assert json_path.exists()
            
            # Verify JSON content
            with open(json_path) as f:
                loaded = json.load(f)
                assert loaded["baseline"]["precision"] == 0.5
                assert loaded["hybrid"]["recall"] == 0.7
    
    def test_save_results_csv(self):
        """Test saving results to CSV file."""
        harness = self._create_harness()
        
        results = {
            "metadata": {"collection": "test"},
            "baseline": {
                "precision": 0.5,
                "recall": 0.5,
                "f1_score": 0.5,
                "reduction_ratio": 95.0,
                "throughput": 100.0,
                "execution_time": 1.0,
                "true_positives": 1,
                "false_positives": 1,
                "false_negatives": 1
            },
            "hybrid": {
                "precision": 0.6,
                "recall": 0.7,
                "f1_score": 0.65,
                "reduction_ratio": 96.0,
                "throughput": 120.0,
                "execution_time": 1.2,
                "true_positives": 2,
                "false_positives": 1,
                "false_negatives": 0
            },
            "improvements": {
                "precision_delta": 0.1,
                "recall_delta": 0.2,
                "f1_delta": 0.15,
                "precision_pct_change": 20.0,
                "recall_pct_change": 40.0,
                "f1_pct_change": 30.0,
                "reduction_ratio_delta": 1.0,
                "throughput_delta": 20.0,
                "execution_time_delta": 0.2
            }
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_files = harness.save_results(results, tmpdir)
            
            assert "csv" in saved_files
            csv_path = Path(saved_files["csv"])
            assert csv_path.exists()
            
            # Verify CSV has correct structure
            with open(csv_path) as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                assert len(rows) > 1  # Header + data rows
                assert rows[0][0] == "Metric"
                assert "Precision" in [row[0] for row in rows]
    
    def test_reduction_ratio_calculation(self):
        """Test reduction ratio calculation."""
        harness = self._create_harness()
        
        # 100 records = 4950 possible comparisons
        # If we generate 100 candidate pairs, reduction = (4950 - 100) / 4950 * 100
        candidate_pairs = [{"record_a_id": str(i), "record_b_id": str(i+1)} for i in range(100)]
        
        metrics = harness._calculate_metrics(
            "test",
            candidate_pairs,
            execution_time=1.0
        )
        
        # Should have high reduction ratio (>95%)
        assert metrics.reduction_ratio > 95.0
    
    def _create_harness(self):
        """Create a test harness with mock ground truth."""
        db_manager = Mock(spec=DatabaseManager)
        db = Mock()
        collection = Mock()
        collection.count.return_value = 100
        db.collection.return_value = collection
        db_manager.get_database.return_value = db
        
        ground_truth = [
            {"record_a_id": "1", "record_b_id": "2", "is_match": True},
            {"record_a_id": "3", "record_b_id": "4", "is_match": True},
            {"record_a_id": "5", "record_b_id": "6", "is_match": False}
        ]
        
        return ABEvaluationHarness(
            db_manager=db_manager,
            collection_name="test_collection",
            ground_truth=ground_truth
        )


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_ground_truth(self):
        """Test handling of empty ground truth."""
        db_manager = Mock(spec=DatabaseManager)
        db = Mock()
        collection = Mock()
        collection.count.return_value = 100
        db.collection.return_value = collection
        db_manager.get_database.return_value = db
        
        harness = ABEvaluationHarness(
            db_manager=db_manager,
            collection_name="test",
            ground_truth=[]
        )
        
        # Should handle empty ground truth gracefully
        metrics = harness._calculate_metrics(
            "test",
            [{"record_a_id": "1", "record_b_id": "2"}],
            execution_time=1.0
        )
        
        assert metrics.total_true_matches == 0
        assert metrics.recall == 0.0  # No true matches to recall
    
    def test_blocking_function_returns_list(self):
        """Test handling when blocking function returns list directly."""
        harness = self._create_harness()
        
        def blocking_returns_list():
            return [
                {"record_a_id": "1", "record_b_id": "2"}
            ]
        
        metrics = harness.evaluate_blocking_strategy("test", blocking_returns_list)
        
        assert metrics.total_candidates == 1
    
    def test_blocking_function_error(self):
        """Test error handling when blocking function fails."""
        harness = self._create_harness()
        
        def failing_blocking():
            raise ValueError("Blocking failed")
        
        with pytest.raises(ValueError, match="Blocking failed"):
            harness.evaluate_blocking_strategy("test", failing_blocking)
    
    def _create_harness(self):
        """Create a test harness."""
        db_manager = Mock(spec=DatabaseManager)
        db = Mock()
        collection = Mock()
        collection.count.return_value = 100
        db.collection.return_value = collection
        db_manager.get_database.return_value = db
        
        return ABEvaluationHarness(
            db_manager=db_manager,
            collection_name="test",
            ground_truth=[
                {"record_a_id": "1", "record_b_id": "2", "is_match": True}
            ]
        )
