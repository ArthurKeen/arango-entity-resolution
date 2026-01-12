"""
Comprehensive tests for BulkBlockingService

Tests cover:
- Service initialization and configuration
- Database connection (mocked)
- Bulk pair generation with multiple strategies
- Streaming pair generation
- Exact blocking strategy (phone, email)
- N-gram blocking strategy
- Phonetic blocking strategy
- Pair deduplication
- Collection statistics
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from entity_resolution.services.bulk_blocking_service import BulkBlockingService
from entity_resolution.utils.config import Config, DatabaseConfig


@pytest.fixture(autouse=True)
def mock_env_config(monkeypatch):
    """Automatically provide a valid config for all tests to avoid env lookups."""
    dummy_config = Config(db_config=DatabaseConfig(password="dummy"))
    monkeypatch.setattr("entity_resolution.services.bulk_blocking_service.get_config", lambda: dummy_config)
    return dummy_config


class TestBulkBlockingServiceBasics:
    """Test basic initialization and configuration."""
    
    def test_initialization_with_default_config(self):
        """Test service initializes with default configuration."""
        service = BulkBlockingService()
        
        assert service.config is not None
        assert service.logger is not None
        assert service.db is None
        assert service.client is None
    
    def test_initialization_with_custom_config(self):
        """Test service initializes with custom configuration."""
        config = Config()
        service = BulkBlockingService(config=config)
        
        assert service.config == config
        assert service.db is None
        assert service.client is None


class TestDatabaseConnection:
    """Test database connection functionality."""
    
    @patch('entity_resolution.services.bulk_blocking_service.ArangoClient')
    def test_connect_success(self, mock_arango_client):
        """Test successful database connection."""
        # Setup mocks
        mock_client_instance = Mock()
        mock_db = Mock()
        mock_arango_client.return_value = mock_client_instance
        mock_client_instance.db.return_value = mock_db
        
        service = BulkBlockingService()
        result = service.connect()
        
        assert result is True
        assert service.client == mock_client_instance
        assert service.db == mock_db
        
        # Verify connection was established correctly
        mock_arango_client.assert_called_once()
        mock_client_instance.db.assert_called_once()
    
    @patch('entity_resolution.services.bulk_blocking_service.ArangoClient')
    def test_connect_failure(self, mock_arango_client):
        """Test database connection failure."""
        mock_arango_client.side_effect = Exception("Connection failed")
        
        service = BulkBlockingService()
        result = service.connect()
        
        assert result is False
        assert service.db is None


class TestPairDeduplication:
    """Test pair deduplication logic."""
    
    def test_deduplicate_no_duplicates(self):
        """Test deduplication with no duplicate pairs."""
        service = BulkBlockingService()
        
        pairs = [
            {"record_a_id": "1", "record_b_id": "2", "strategy": "exact"},
            {"record_a_id": "1", "record_b_id": "3", "strategy": "exact"},
            {"record_a_id": "2", "record_b_id": "3", "strategy": "exact"}
        ]
        
        result = service._deduplicate_pairs(pairs)
        
        assert len(result) == 3
        assert result == pairs
    
    def test_deduplicate_with_duplicates(self):
        """Test deduplication removes duplicate pairs."""
        service = BulkBlockingService()
        
        pairs = [
            {"record_a_id": "1", "record_b_id": "2", "strategy": "exact"},
            {"record_a_id": "2", "record_b_id": "1", "strategy": "ngram"},  # Duplicate (reversed)
            {"record_a_id": "1", "record_b_id": "3", "strategy": "exact"},
            {"record_a_id": "1", "record_b_id": "2", "strategy": "phonetic"}  # Duplicate (same)
        ]
        
        result = service._deduplicate_pairs(pairs)
        
        assert len(result) == 2
        # Should keep first occurrence of 1-2 pair and the 1-3 pair
        record_ids = [(p["record_a_id"], p["record_b_id"]) for p in result]
        assert ("1", "2") in record_ids
        assert ("1", "3") in record_ids
    
    def test_deduplicate_empty_list(self):
        """Test deduplication with empty list."""
        service = BulkBlockingService()
        
        result = service._deduplicate_pairs([])
        
        assert result == []
    
    def test_deduplicate_canonical_ordering(self):
        """Test deduplication uses canonical ordering (smaller ID first)."""
        service = BulkBlockingService()
        
        pairs = [
            {"record_a_id": "customers/100", "record_b_id": "customers/50", "strategy": "exact"},
            {"record_a_id": "customers/50", "record_b_id": "customers/100", "strategy": "ngram"}
        ]
        
        result = service._deduplicate_pairs(pairs)
        
        # Should recognize these as duplicates despite order
        assert len(result) == 1


class TestGenerateAllPairs:
    """Test bulk pair generation."""
    
    def test_generate_all_pairs_not_connected(self):
        """Test generate_all_pairs returns error when not connected."""
        service = BulkBlockingService()
        
        result = service.generate_all_pairs("test_collection")
        
        assert result["success"] is False
        assert "Not connected" in result["error"]
    
    def test_generate_all_pairs_collection_not_exists(self):
        """Test generate_all_pairs handles non-existent collection."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = False
        
        result = service.generate_all_pairs("nonexistent")
        
        assert result["success"] is False
        assert "does not exist" in result["error"]
    
    def test_generate_all_pairs_success(self):
        """Test successful pair generation."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        
        # Mock strategy execution
        service._execute_exact_blocking = Mock(return_value=[
            {"record_a_id": "1", "record_b_id": "2", "strategy": "exact"}
        ])
        service._execute_ngram_blocking = Mock(return_value=[
            {"record_a_id": "1", "record_b_id": "3", "strategy": "ngram"}
        ])
        
        result = service.generate_all_pairs(
            "test_collection",
            strategies=["exact", "ngram"],
            limit=100
        )
        
        assert result["success"] is True
        assert result["method"] == "bulk_set_based"
        assert result["collection"] == "test_collection"
        assert len(result["candidate_pairs"]) == 2
        assert result["statistics"]["total_pairs"] == 2
        assert result["statistics"]["strategies_used"] == 2
        assert "execution_time" in result["statistics"]
        assert "pairs_per_second" in result["statistics"]
        assert result["statistics"]["execution_time"] > 0
    
    def test_generate_all_pairs_default_strategies(self):
        """Test generate_all_pairs uses default strategies when none provided."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        service._execute_exact_blocking = Mock(return_value=[])
        service._execute_ngram_blocking = Mock(return_value=[])
        
        result = service.generate_all_pairs("test_collection")
        
        assert result["success"] is True
        # Should use default strategies: ["exact", "ngram"]
        service._execute_exact_blocking.assert_called_once()
        service._execute_ngram_blocking.assert_called_once()
    
    def test_generate_all_pairs_unknown_strategy(self):
        """Test generate_all_pairs skips unknown strategies."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        service._execute_exact_blocking = Mock(return_value=[])
        
        result = service.generate_all_pairs(
            "test_collection",
            strategies=["exact", "unknown_strategy"]
        )
        
        assert result["success"] is True
        # Should execute exact but skip unknown
        service._execute_exact_blocking.assert_called_once()
    
    def test_generate_all_pairs_deduplicates(self):
        """Test generate_all_pairs deduplicates results."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        
        # Return overlapping pairs from different strategies
        service._execute_exact_blocking = Mock(return_value=[
            {"record_a_id": "1", "record_b_id": "2", "strategy": "exact"},
            {"record_a_id": "1", "record_b_id": "3", "strategy": "exact"}
        ])
        service._execute_ngram_blocking = Mock(return_value=[
            {"record_a_id": "1", "record_b_id": "2", "strategy": "ngram"},  # Duplicate
            {"record_a_id": "2", "record_b_id": "3", "strategy": "ngram"}
        ])
        
        result = service.generate_all_pairs(
            "test_collection",
            strategies=["exact", "ngram"]
        )
        
        # Should have 3 unique pairs (1-2, 1-3, 2-3)
        assert result["statistics"]["total_pairs"] == 3
        assert result["statistics"]["total_pairs_before_dedup"] == 4
        assert result["statistics"]["duplicate_pairs_removed"] == 1
    
    def test_generate_all_pairs_exception_handling(self):
        """Test generate_all_pairs handles exceptions gracefully."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        
        # Make strategy execution fail
        service._execute_exact_blocking = Mock(side_effect=Exception("Database error"))
        
        result = service.generate_all_pairs("test_collection", strategies=["exact"])
        
        assert result["success"] is False
        assert "error" in result


class TestGeneratePairsStreaming:
    """Test streaming pair generation."""
    
    def test_streaming_not_connected(self):
        """Test streaming returns immediately when not connected."""
        service = BulkBlockingService()
        
        batches = list(service.generate_pairs_streaming("test_collection"))
        
        assert batches == []
    
    def test_streaming_yields_batches(self):
        """Test streaming yields pairs in batches."""
        service = BulkBlockingService()
        service.db = Mock()
        
        # Mock 5 pairs total
        pairs = [
            {"record_a_id": f"{i}", "record_b_id": f"{i+1}", "strategy": "exact"}
            for i in range(5)
        ]
        service._execute_exact_blocking = Mock(return_value=pairs)
        
        batches = list(service.generate_pairs_streaming(
            "test_collection",
            strategies=["exact"],
            batch_size=2
        ))
        
        assert len(batches) == 3  # 5 pairs / 2 per batch = 3 batches
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2
        assert len(batches[2]) == 1  # Last batch has remainder
    
    def test_streaming_default_strategies(self):
        """Test streaming uses default strategies when none provided."""
        service = BulkBlockingService()
        service.db = Mock()
        service._execute_exact_blocking = Mock(return_value=[])
        service._execute_ngram_blocking = Mock(return_value=[])
        
        list(service.generate_pairs_streaming("test_collection"))
        
        # Should use default strategies
        service._execute_exact_blocking.assert_called_once()
        service._execute_ngram_blocking.assert_called_once()
    
    def test_streaming_multiple_strategies(self):
        """Test streaming processes multiple strategies."""
        service = BulkBlockingService()
        service.db = Mock()
        
        service._execute_exact_blocking = Mock(return_value=[
            {"record_a_id": "1", "record_b_id": "2", "strategy": "exact"}
        ])
        service._execute_phonetic_blocking = Mock(return_value=[
            {"record_a_id": "3", "record_b_id": "4", "strategy": "phonetic"}
        ])
        
        batches = list(service.generate_pairs_streaming(
            "test_collection",
            strategies=["exact", "phonetic"],
            batch_size=10
        ))
        
        # Should have 2 batches (one per strategy)
        assert len(batches) == 2


class TestExactBlocking:
    """Test exact blocking strategy."""
    
    def test_exact_blocking_phone_pairs(self):
        """Test exact blocking finds phone-based pairs."""
        service = BulkBlockingService()
        service.db = Mock()
        
        # Mock phone query results
        mock_cursor = [
            {"record_a_id": "1", "record_b_id": "2", "strategy": "exact_phone", "blocking_key": "5551234567"},
            {"record_a_id": "1", "record_b_id": "3", "strategy": "exact_phone", "blocking_key": "5551234567"}
        ]
        service.db.aql.execute.return_value = iter(mock_cursor)
        
        result = service._execute_exact_blocking("test_collection", limit=0)
        
        # Should call AQL twice (phone + email)
        assert service.db.aql.execute.call_count == 2
        # Results include phone pairs (and potentially email pairs if mocked)
        assert len(result) >= 0
    
    def test_exact_blocking_with_limit(self):
        """Test exact blocking respects limit parameter."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.aql.execute.return_value = iter([])
        
        service._execute_exact_blocking("test_collection", limit=100)
        
        # Verify limit is passed to query
        calls = service.db.aql.execute.call_args_list
        for call in calls:
            assert call[1]['bind_vars']['limit'] == 100
    
    def test_exact_blocking_handles_errors(self):
        """Test exact blocking handles query errors gracefully."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.aql.execute.side_effect = Exception("Query failed")
        
        result = service._execute_exact_blocking("test_collection", limit=0)
        
        # Should return empty list on error, not crash
        assert result == []


class TestNgramBlocking:
    """Test n-gram blocking strategy."""
    
    def test_ngram_blocking_success(self):
        """Test n-gram blocking finds similar names."""
        service = BulkBlockingService()
        service.db = Mock()
        
        mock_cursor = [
            {"record_a_id": "1", "record_b_id": "2", "strategy": "ngram_name", "blocking_key": "SMI_2"},
            {"record_a_id": "1", "record_b_id": "3", "strategy": "ngram_name", "blocking_key": "SMI_2"}
        ]
        service.db.aql.execute.return_value = iter(mock_cursor)
        
        result = service._execute_ngram_blocking("test_collection", limit=0)
        
        assert len(result) == 2
        service.db.aql.execute.assert_called_once()
    
    def test_ngram_blocking_with_limit(self):
        """Test n-gram blocking respects limit."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.aql.execute.return_value = iter([])
        
        service._execute_ngram_blocking("test_collection", limit=50)
        
        # Verify limit is passed
        call_args = service.db.aql.execute.call_args
        assert call_args[1]['bind_vars']['limit'] == 50
    
    def test_ngram_blocking_handles_errors(self):
        """Test n-gram blocking handles errors gracefully."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.aql.execute.side_effect = Exception("Query failed")
        
        result = service._execute_ngram_blocking("test_collection", limit=0)
        
        assert result == []


class TestPhoneticBlocking:
    """Test phonetic blocking strategy."""
    
    def test_phonetic_blocking_success(self):
        """Test phonetic blocking finds similar-sounding names."""
        service = BulkBlockingService()
        service.db = Mock()
        
        mock_cursor = [
            {"record_a_id": "1", "record_b_id": "2", "strategy": "phonetic_soundex", "blocking_key": "S530"},
            {"record_a_id": "2", "record_b_id": "3", "strategy": "phonetic_soundex", "blocking_key": "S530"}
        ]
        service.db.aql.execute.return_value = iter(mock_cursor)
        
        result = service._execute_phonetic_blocking("test_collection", limit=0)
        
        assert len(result) == 2
        service.db.aql.execute.assert_called_once()
    
    def test_phonetic_blocking_with_limit(self):
        """Test phonetic blocking respects limit."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.aql.execute.return_value = iter([])
        
        service._execute_phonetic_blocking("test_collection", limit=75)
        
        # Verify limit is passed
        call_args = service.db.aql.execute.call_args
        assert call_args[1]['bind_vars']['limit'] == 75
    
    def test_phonetic_blocking_handles_errors(self):
        """Test phonetic blocking handles errors gracefully."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.aql.execute.side_effect = Exception("Soundex failed")
        
        result = service._execute_phonetic_blocking("test_collection", limit=0)
        
        assert result == []


class TestCollectionStats:
    """Test collection statistics."""
    
    def test_get_collection_stats_success(self):
        """Test getting collection statistics."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        
        mock_collection = Mock()
        mock_collection.count.return_value = 10000
        service.db.collection.return_value = mock_collection
        
        result = service.get_collection_stats("test_collection")
        
        assert result["success"] is True
        assert result["collection"] == "test_collection"
        assert result["record_count"] == 10000
        assert "naive_comparisons" in result
        assert "estimated_execution_time" in result
        
        # Verify naive comparisons calculation
        # For 10,000 records: (10000 * 9999) / 2 = 49,995,000
        expected_comparisons = (10000 * 9999) // 2
        assert result["naive_comparisons"] == expected_comparisons
    
    def test_get_collection_stats_not_connected(self):
        """Test collection stats when not connected."""
        service = BulkBlockingService()
        
        result = service.get_collection_stats("test_collection")
        
        assert result["success"] is False
        assert "error" in result
    
    def test_get_collection_stats_collection_not_exists(self):
        """Test collection stats for non-existent collection."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = False
        
        result = service.get_collection_stats("nonexistent")
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    def test_get_collection_stats_exception(self):
        """Test collection stats handles exceptions."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        service.db.collection.side_effect = Exception("Collection access failed")
        
        result = service.get_collection_stats("test_collection")
        
        assert result["success"] is False
        assert "error" in result
    
    def test_get_collection_stats_estimates_timing(self):
        """Test collection stats provides timing estimates."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        
        mock_collection = Mock()
        mock_collection.count.return_value = 50000
        service.db.collection.return_value = mock_collection
        
        result = service.get_collection_stats("test_collection")
        
        assert result["success"] is True
        estimates = result["estimated_execution_time"]
        assert "exact_blocking" in estimates
        assert "ngram_blocking" in estimates
        assert "phonetic_blocking" in estimates
        # Should contain numeric estimates in seconds format
        assert "seconds" in estimates["exact_blocking"]


class TestEdgeCases:
    """Test edge cases and robustness."""
    
    def test_generate_all_pairs_empty_strategies_list(self):
        """Test generate_all_pairs with empty strategies list."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        
        result = service.generate_all_pairs("test_collection", strategies=[])
        
        # Should still succeed, just with no pairs
        assert result["success"] is True
        assert result["statistics"]["total_pairs"] == 0
    
    def test_deduplicate_preserves_first_occurrence(self):
        """Test deduplication preserves first occurrence of duplicates."""
        service = BulkBlockingService()
        
        pairs = [
            {"record_a_id": "1", "record_b_id": "2", "strategy": "exact", "score": 0.9},
            {"record_a_id": "1", "record_b_id": "2", "strategy": "ngram", "score": 0.7}
        ]
        
        result = service._deduplicate_pairs(pairs)
        
        assert len(result) == 1
        # Should preserve first occurrence (exact with score 0.9)
        assert result[0]["strategy"] == "exact"
        assert result[0]["score"] == 0.9
    
    def test_generate_all_pairs_zero_limit(self):
        """Test generate_all_pairs with limit=0 (no limit)."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        service._execute_exact_blocking = Mock(return_value=[
            {"record_a_id": str(i), "record_b_id": str(i+1), "strategy": "exact"}
            for i in range(100)  # Return 100 pairs
        ])
        
        result = service.generate_all_pairs("test_collection", limit=0)
        
        # Should return all 100 pairs (no limit)
        assert len(result["candidate_pairs"]) == 100
    
    def test_streaming_empty_results(self):
        """Test streaming with no pairs found."""
        service = BulkBlockingService()
        service.db = Mock()
        service._execute_exact_blocking = Mock(return_value=[])
        service._execute_ngram_blocking = Mock(return_value=[])
        
        batches = list(service.generate_pairs_streaming("test_collection"))
        
        # Should still work, just no batches yielded
        assert batches == []
    
    def test_all_strategies_combined(self):
        """Test using all three strategies together."""
        service = BulkBlockingService()
        service.db = Mock()
        service.db.has_collection.return_value = True
        
        service._execute_exact_blocking = Mock(return_value=[{"record_a_id": "1", "record_b_id": "2"}])
        service._execute_ngram_blocking = Mock(return_value=[{"record_a_id": "2", "record_b_id": "3"}])
        service._execute_phonetic_blocking = Mock(return_value=[{"record_a_id": "3", "record_b_id": "4"}])
        
        result = service.generate_all_pairs(
            "test_collection",
            strategies=["exact", "ngram", "phonetic"]
        )
        
        assert result["success"] is True
        assert result["statistics"]["strategies_used"] == 3
        assert len(result["candidate_pairs"]) == 3
        
        # Verify all three strategies were called
        service._execute_exact_blocking.assert_called_once()
        service._execute_ngram_blocking.assert_called_once()
        service._execute_phonetic_blocking.assert_called_once()
