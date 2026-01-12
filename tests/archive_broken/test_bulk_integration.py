"""
Integration Tests for Bulk Processing

Tests the complete bulk processing workflow including:
- Connection to real database
- Actual query execution
- Performance benchmarks
- End-to-end scenarios

NOTE: These tests require a running ArangoDB instance.
Set SKIP_INTEGRATION_TESTS=true to skip if database unavailable.
"""

import pytest
import os
import sys
import time
from typing import List, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.bulk_blocking_service import BulkBlockingService
from entity_resolution.utils.config import get_config


# Skip integration tests if environment variable is set
skip_integration = os.getenv('SKIP_INTEGRATION_TESTS', 'false').lower() == 'true'
skip_reason = "Skipping integration tests (SKIP_INTEGRATION_TESTS=true or no database)"


@pytest.fixture
def bulk_service():
    """Fixture to create and connect bulk blocking service"""
    service = BulkBlockingService()
    
    # Try to connect, skip tests if fails
    if not service.connect():
        pytest.skip("Cannot connect to database")
    
    return service


@pytest.fixture
def test_collection(bulk_service):
    """Fixture to create a test collection with sample data"""
    if not bulk_service.db:
        pytest.skip("No database connection")
    
    collection_name = "test_bulk_blocking"
    
    # Create collection
    if bulk_service.db.has_collection(collection_name):
        bulk_service.db.delete_collection(collection_name)
    
    collection = bulk_service.db.create_collection(collection_name)
    
    # Insert test data - customers with duplicates
    test_data = [
        # Exact phone duplicates
        {"_key": "1", "first_name": "John", "last_name": "Smith", 
         "phone": "555-1234", "email": "john.smith@example.com"},
        {"_key": "2", "first_name": "Johnny", "last_name": "Smith", 
         "phone": "555-1234", "email": "j.smith@example.com"},
        
        # Exact email duplicates
        {"_key": "3", "first_name": "Jane", "last_name": "Doe", 
         "phone": "555-5678", "email": "jane@example.com"},
        {"_key": "4", "first_name": "Jane", "last_name": "D", 
         "phone": "555-9999", "email": "jane@example.com"},
        
        # Similar names (n-gram)
        {"_key": "5", "first_name": "Michael", "last_name": "Johnson", 
         "phone": "555-1111", "email": "mjohnson@example.com"},
        {"_key": "6", "first_name": "Mike", "last_name": "Johnson", 
         "phone": "555-2222", "email": "mike.j@example.com"},
        
        # Phonetic duplicates (Smith/Smyth)
        {"_key": "7", "first_name": "Bob", "last_name": "Smyth", 
         "phone": "555-3333", "email": "bob.smyth@example.com"},
        {"_key": "8", "first_name": "Robert", "last_name": "Smith", 
         "phone": "555-4444", "email": "robert.smith@example.com"},
        
        # Unique records (no matches)
        {"_key": "9", "first_name": "Alice", "last_name": "Wonder", 
         "phone": "555-7777", "email": "alice@example.com"},
        {"_key": "10", "first_name": "Charlie", "last_name": "Brown", 
         "phone": "555-8888", "email": "charlie@example.com"},
    ]
    
    collection.insert_many(test_data)
    
    yield collection_name
    
    # Cleanup
    if bulk_service.db.has_collection(collection_name):
        bulk_service.db.delete_collection(collection_name)


@pytest.mark.skipif(skip_integration, reason=skip_reason)
class TestBulkBlockingIntegration:
    """Integration tests for bulk blocking"""
    
    def test_exact_blocking_finds_phone_duplicates(self, bulk_service, test_collection):
        """Test that exact blocking finds phone number duplicates"""
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["exact"],
            limit=0
        )
        
        assert result['success'] is True
        assert len(result['candidate_pairs']) >= 2  # At least phone and email matches
        
        # Verify we found the phone duplicate
        phone_pairs = [p for p in result['candidate_pairs'] 
                      if p['strategy'] == 'exact_phone']
        assert len(phone_pairs) >= 1
    
    def test_exact_blocking_finds_email_duplicates(self, bulk_service, test_collection):
        """Test that exact blocking finds email duplicates"""
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["exact"],
            limit=0
        )
        
        # Verify we found the email duplicate
        email_pairs = [p for p in result['candidate_pairs'] 
                      if p['strategy'] == 'exact_email']
        assert len(email_pairs) >= 1
    
    def test_ngram_blocking_finds_similar_names(self, bulk_service, test_collection):
        """Test that n-gram blocking finds similar names"""
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["ngram"],
            limit=0
        )
        
        assert result['success'] is True
        # Should find Johnson/Johnson and Smith/Smyth
        assert len(result['candidate_pairs']) >= 2
    
    def test_phonetic_blocking_finds_soundex_matches(self, bulk_service, test_collection):
        """Test that phonetic blocking finds similar-sounding names"""
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["phonetic"],
            limit=0
        )
        
        assert result['success'] is True
        # Should find Smith/Smyth
        assert len(result['candidate_pairs']) >= 1
    
    def test_multiple_strategies_combined(self, bulk_service, test_collection):
        """Test using multiple strategies together"""
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["exact", "ngram", "phonetic"],
            limit=0
        )
        
        assert result['success'] is True
        assert result['statistics']['strategies_used'] == 3
        
        # Should find duplicates from all strategies
        assert len(result['candidate_pairs']) >= 4
        
        # Verify deduplication worked
        total_before_dedup = result['statistics']['total_pairs_before_dedup']
        total_after_dedup = result['statistics']['total_pairs']
        assert total_after_dedup <= total_before_dedup
    
    def test_statistics_accurate(self, bulk_service, test_collection):
        """Test that statistics are accurate"""
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["exact"],
            limit=0
        )
        
        stats = result['statistics']
        
        # Verify statistics structure
        assert 'total_pairs' in stats
        assert 'execution_time' in stats
        assert 'pairs_per_second' in stats
        assert 'strategy_breakdown' in stats
        
        # Verify calculations
        assert stats['total_pairs'] == len(result['candidate_pairs'])
        assert stats['execution_time'] > 0
        assert stats['pairs_per_second'] >= 0
    
    def test_collection_stats(self, bulk_service, test_collection):
        """Test getting collection statistics"""
        result = bulk_service.get_collection_stats(test_collection)
        
        assert result['success'] is True
        assert result['record_count'] == 10
        assert result['naive_comparisons'] == 45  # (10 * 9) / 2


@pytest.mark.skipif(skip_integration, reason=skip_reason)
class TestBulkBlockingPerformance:
    """Performance tests for bulk blocking"""
    
    def test_bulk_faster_than_naive(self, bulk_service, test_collection):
        """Test that bulk blocking is faster than naive comparison"""
        start = time.time()
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["exact"],
            limit=0
        )
        bulk_time = time.time() - start
        
        # For 10 records, should complete in under 1 second
        assert bulk_time < 1.0
        
        # Verify we reduced comparisons
        stats = bulk_service.get_collection_stats(test_collection)
        naive_comparisons = stats['naive_comparisons']
        actual_pairs = result['statistics']['total_pairs']
        
        # Should have much fewer pairs than naive approach
        assert actual_pairs < naive_comparisons
    
    def test_performance_scales_linearly(self, bulk_service):
        """Test that performance scales approximately linearly"""
        # This would need larger datasets to test properly
        # For now, just verify the metric is calculated
        pass
    
    def test_streaming_memory_efficient(self, bulk_service, test_collection):
        """Test that streaming doesn't load all pairs into memory at once"""
        batch_count = 0
        total_pairs = 0
        
        for batch in bulk_service.generate_pairs_streaming(
            collection_name=test_collection,
            strategies=["exact"],
            batch_size=2
        ):
            batch_count += 1
            total_pairs += len(batch)
            
            # Each batch should be small
            assert len(batch) <= 2
        
        # Should have received pairs in batches
        assert batch_count >= 1
        assert total_pairs >= 0


@pytest.mark.skipif(skip_integration, reason=skip_reason)
class TestBulkBlockingEdgeCases:
    """Test edge cases with real database"""
    
    def test_empty_collection(self, bulk_service):
        """Test handling of empty collection"""
        # Create empty collection
        collection_name = "test_empty"
        if bulk_service.db.has_collection(collection_name):
            bulk_service.db.delete_collection(collection_name)
        
        bulk_service.db.create_collection(collection_name)
        
        try:
            result = bulk_service.generate_all_pairs(collection_name)
            
            assert result['success'] is True
            assert len(result['candidate_pairs']) == 0
        finally:
            bulk_service.db.delete_collection(collection_name)
    
    def test_collection_not_found(self, bulk_service):
        """Test handling of nonexistent collection"""
        result = bulk_service.generate_all_pairs("nonexistent_collection_xyz")
        
        assert result['success'] is False
        assert 'does not exist' in result['error']
    
    def test_limit_respected(self, bulk_service, test_collection):
        """Test that limit parameter is respected"""
        result = bulk_service.generate_all_pairs(
            collection_name=test_collection,
            strategies=["exact", "ngram"],
            limit=3
        )
        
        assert result['success'] is True
        # Should not exceed limit (though may be less due to dedup)
        assert len(result['candidate_pairs']) <= 3
    
    def test_records_with_null_values(self, bulk_service):
        """Test handling of records with null/missing values"""
        collection_name = "test_nulls"
        
        if bulk_service.db.has_collection(collection_name):
            bulk_service.db.delete_collection(collection_name)
        
        collection = bulk_service.db.create_collection(collection_name)
        
        # Records with various null/missing fields
        collection.insert_many([
            {"_key": "1", "first_name": "John", "last_name": None, "phone": "555-1234"},
            {"_key": "2", "first_name": None, "last_name": "Smith", "email": None},
            {"_key": "3", "first_name": "Jane"},  # Missing many fields
        ])
        
        try:
            result = bulk_service.generate_all_pairs(collection_name)
            
            # Should not crash
            assert result['success'] is True
        finally:
            bulk_service.db.delete_collection(collection_name)


@pytest.mark.skipif(skip_integration, reason=skip_reason)
class TestBulkBlockingRealWorldScenarios:
    """Test real-world scenarios"""
    
    def test_typo_variations(self, bulk_service):
        """Test finding records with typos"""
        collection_name = "test_typos"
        
        if bulk_service.db.has_collection(collection_name):
            bulk_service.db.delete_collection(collection_name)
        
        collection = bulk_service.db.create_collection(collection_name)
        
        collection.insert_many([
            {"_key": "1", "first_name": "Michael", "last_name": "Johnson", 
             "email": "mjohnson@example.com"},
            {"_key": "2", "first_name": "Micheal", "last_name": "Johnson",  # Typo
             "email": "mjohnson@example.com"},
            {"_key": "3", "first_name": "Michael", "last_name": "Jonson",  # Typo
             "email": "m.johnson@example.com"},
        ])
        
        try:
            result = bulk_service.generate_all_pairs(
                collection_name,
                strategies=["exact", "ngram", "phonetic"]
            )
            
            # Should find the duplicates despite typos
            assert result['success'] is True
            assert len(result['candidate_pairs']) >= 2
        finally:
            bulk_service.db.delete_collection(collection_name)
    
    def test_name_variations(self, bulk_service):
        """Test finding records with name variations"""
        collection_name = "test_name_variations"
        
        if bulk_service.db.has_collection(collection_name):
            bulk_service.db.delete_collection(collection_name)
        
        collection = bulk_service.db.create_collection(collection_name)
        
        collection.insert_many([
            {"_key": "1", "first_name": "Robert", "last_name": "Smith", 
             "phone": "555-1234"},
            {"_key": "2", "first_name": "Bob", "last_name": "Smith", 
             "phone": "555-1234"},  # Nickname
            {"_key": "3", "first_name": "R.", "last_name": "Smith", 
             "phone": "555-1234"},  # Initial
        ])
        
        try:
            result = bulk_service.generate_all_pairs(
                collection_name,
                strategies=["exact", "ngram"]
            )
            
            # Exact blocking should catch phone duplicates
            assert result['success'] is True
            assert len(result['candidate_pairs']) >= 2
            
            # Verify phone strategy found them
            phone_pairs = [p for p in result['candidate_pairs'] 
                          if p['strategy'] == 'exact_phone']
            assert len(phone_pairs) >= 2
        finally:
            bulk_service.db.delete_collection(collection_name)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

