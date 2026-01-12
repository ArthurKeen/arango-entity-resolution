"""
Enhanced Unit Tests for SimilarityService

Comprehensive tests for similarity computation, including:
- String similarity metrics (Levenshtein, Jaro-Winkler, etc.)
- Composite scoring
- Performance
- Edge cases
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.similarity_service import SimilarityService


class TestSimilarityServiceInitialization:
    """Test service initialization"""
    
    def test_initialization(self):
        """Test service initializes correctly"""
        service = SimilarityService()
        
        assert service is not None
        assert service.config is not None


class TestStringSimilarityMetrics:
    """Test individual string similarity metrics"""
    
    def test_levenshtein_exact_match(self):
        """Test Levenshtein distance for exact matches"""
        service = SimilarityService()
        
        similarity = service.levenshtein_similarity("test", "test")
        
        assert similarity == 1.0
    
    def test_levenshtein_different_strings(self):
        """Test Levenshtein distance for different strings"""
        service = SimilarityService()
        
        similarity = service.levenshtein_similarity("test", "toast")
        
        # "test" vs "toast": 2 edits needed, similarity should be < 1.0
        assert 0.0 < similarity < 1.0
    
    def test_levenshtein_empty_strings(self):
        """Test Levenshtein distance with empty strings"""
        service = SimilarityService()
        
        similarity = service.levenshtein_similarity("", "")
        
        # Empty strings should be considered identical
        assert similarity == 1.0
    
    def test_jaro_winkler_exact_match(self):
        """Test Jaro-Winkler for exact matches"""
        service = SimilarityService()
        
        similarity = service.jaro_winkler_similarity("test", "test")
        
        assert similarity == 1.0
    
    def test_jaro_winkler_similar_strings(self):
        """Test Jaro-Winkler for similar strings"""
        service = SimilarityService()
        
        # Jaro-Winkler is good for short strings with common prefixes
        similarity = service.jaro_winkler_similarity("martha", "marhta")
        
        assert similarity > 0.8
    
    def test_cosine_similarity(self):
        """Test cosine similarity"""
        service = SimilarityService()
        
        similarity = service.cosine_similarity("test string", "test string")
        
        assert similarity == 1.0
    
    def test_jaccard_similarity(self):
        """Test Jaccard similarity"""
        service = SimilarityService()
        
        similarity = service.jaccard_similarity("test string", "test string")
        
        assert similarity == 1.0


class TestCompositeSimilarity:
    """Test composite similarity scoring"""
    
    def test_compute_record_similarity(self):
        """Test computing similarity between two records"""
        service = SimilarityService()
        
        record_a = {
            'first_name': 'John',
            'last_name': 'Smith',
            'email': 'john.smith@example.com'
        }
        
        record_b = {
            'first_name': 'John',
            'last_name': 'Smyth',  # Slight variation
            'email': 'john.smith@example.com'
        }
        
        similarity = service.compute_record_similarity(record_a, record_b)
        
        # Should have high similarity due to matching email and first name
        assert similarity > 0.8
    
    def test_weighted_similarity(self):
        """Test that field weights affect similarity scores"""
        service = SimilarityService()
        
        # Email should have higher weight than name
        record_a = {
            'first_name': 'John',
            'last_name': 'Smith',
            'email': 'john.smith@example.com'
        }
        
        record_b = {
            'first_name': 'Jane',  # Different name
            'last_name': 'Doe',
            'email': 'john.smith@example.com'  # Same email
        }
        
        similarity = service.compute_record_similarity(record_a, record_b)
        
        # Should still have decent similarity due to matching email
        assert similarity > 0.5


class TestSimilarityBatchProcessing:
    """Test batch similarity computation"""
    
    def test_compute_similarities_for_pairs(self):
        """Test computing similarities for multiple pairs"""
        service = SimilarityService()
        
        candidate_pairs = [
            {
                'record_a': {'name': 'John Smith', 'email': 'john@example.com'},
                'record_b': {'name': 'J. Smith', 'email': 'john@example.com'}
            },
            {
                'record_a': {'name': 'Jane Doe', 'email': 'jane@example.com'},
                'record_b': {'name': 'Jane D.', 'email': 'jane@example.com'}
            }
        ]
        
        result = service.compute_similarities(candidate_pairs)
        
        assert result['success'] is True
        assert len(result['scored_pairs']) == 2
        assert all('similarity_score' in pair for pair in result['scored_pairs'])


class TestSimilarityEdgeCases:
    """Test edge cases"""
    
    def test_null_values_handled(self):
        """Test that null values are handled gracefully"""
        service = SimilarityService()
        
        record_a = {'name': 'John', 'email': None}
        record_b = {'name': 'John', 'email': None}
        
        # Should not crash
        similarity = service.compute_record_similarity(record_a, record_b)
        
        assert similarity >= 0.0
        assert similarity <= 1.0
    
    def test_missing_fields_handled(self):
        """Test that missing fields are handled"""
        service = SimilarityService()
        
        record_a = {'name': 'John'}
        record_b = {'name': 'John', 'email': 'john@example.com'}
        
        # Should not crash
        similarity = service.compute_record_similarity(record_a, record_b)
        
        assert similarity >= 0.0
    
    def test_empty_records_handled(self):
        """Test that empty records are handled"""
        service = SimilarityService()
        
        record_a = {}
        record_b = {}
        
        # Should not crash
        similarity = service.compute_record_similarity(record_a, record_b)
        
        assert similarity >= 0.0
    
    def test_special_characters_handled(self):
        """Test that special characters are handled"""
        service = SimilarityService()
        
        record_a = {'name': 'John@Smith#123', 'email': 'test@example.com'}
        record_b = {'name': 'John@Smith#123', 'email': 'test@example.com'}
        
        similarity = service.compute_record_similarity(record_a, record_b)
        
        # Should match perfectly
        assert similarity > 0.9


class TestSimilarityThresholds:
    """Test similarity thresholding"""
    
    def test_threshold_filtering(self):
        """Test that pairs below threshold are filtered"""
        service = SimilarityService()
        
        candidate_pairs = [
            {
                'record_a': {'name': 'John Smith'},
                'record_b': {'name': 'John Smith'}
            },
            {
                'record_a': {'name': 'John Smith'},
                'record_b': {'name': 'Completely Different'}
            }
        ]
        
        result = service.compute_similarities(
            candidate_pairs,
            min_similarity=0.7
        )
        
        # Should only return high-similarity pair
        assert len(result['scored_pairs']) < len(candidate_pairs)


class TestSimilarityPerformance:
    """Test performance characteristics"""
    
    def test_similarity_computation_fast(self):
        """Test that similarity computation is reasonably fast"""
        import time
        
        service = SimilarityService()
        
        record_a = {
            'first_name': 'John',
            'last_name': 'Smith',
            'email': 'john.smith@example.com',
            'phone': '555-1234'
        }
        
        record_b = {
            'first_name': 'J.',
            'last_name': 'Smith',
            'email': 'j.smith@example.com',
            'phone': '555-1234'
        }
        
        start = time.time()
        similarity = service.compute_record_similarity(record_a, record_b)
        execution_time = time.time() - start
        
        # Should compute in < 0.01 seconds
        assert execution_time < 0.01
    
    def test_batch_processing_efficient(self):
        """Test that batch processing is efficient"""
        import time
        
        service = SimilarityService()
        
        # Create 100 pairs
        candidate_pairs = [
            {
                'record_a': {'name': f'Person{i}', 'email': f'person{i}@example.com'},
                'record_b': {'name': f'Person{i}', 'email': f'person{i}@example.com'}
            }
            for i in range(100)
        ]
        
        start = time.time()
        result = service.compute_similarities(candidate_pairs)
        execution_time = time.time() - start
        
        # Should process 100 pairs in < 1 second
        assert execution_time < 1.0


class TestSimilarityStatistics:
    """Test statistics generation"""
    
    def test_statistics_generated(self):
        """Test that statistics are generated"""
        service = SimilarityService()
        
        candidate_pairs = [
            {
                'record_a': {'name': 'John'},
                'record_b': {'name': 'John'}
            }
        ]
        
        result = service.compute_similarities(candidate_pairs)
        
        assert 'statistics' in result
        assert 'execution_time' in result['statistics']
        assert 'pairs_processed' in result['statistics']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

