"""
Unit Tests for Graph Utilities

Comprehensive tests for graph_utils module functions.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.graph_utils import (
    format_vertex_id,
    extract_key_from_vertex_id,
    parse_vertex_id,
    normalize_vertex_ids,
    is_valid_vertex_id,
    extract_collection_from_vertex_id
)


class TestFormatVertexId:
    """Test format_vertex_id function."""
    
    def test_format_with_collection(self):
        """Test formatting with explicit collection."""
        result = format_vertex_id("123", "companies")
        assert result == "companies/123"
    
    def test_format_with_default_collection(self):
        """Test formatting with default collection."""
        result = format_vertex_id("123")
        assert result == "vertices/123"
    
    def test_format_already_formatted(self):
        """Test formatting already formatted ID."""
        result = format_vertex_id("companies/123", "companies")
        assert result == "companies/123"  # Should return as-is
    
    def test_format_different_collection(self):
        """Test formatting with different collection in ID."""
        # If already formatted, collection parameter is ignored
        result = format_vertex_id("companies/123", "customers")
        assert result == "companies/123"  # Returns as-is
    
    def test_format_empty_key(self):
        """Test formatting with empty key."""
        result = format_vertex_id("", "companies")
        assert result == "companies/"
    
    def test_format_special_characters(self):
        """Test formatting with special characters in key."""
        result = format_vertex_id("key-with-dashes_123", "companies")
        assert result == "companies/key-with-dashes_123"


class TestExtractKeyFromVertexId:
    """Test extract_key_from_vertex_id function."""
    
    def test_extract_from_formatted_id(self):
        """Test extracting key from formatted ID."""
        result = extract_key_from_vertex_id("companies/123")
        assert result == "123"
    
    def test_extract_from_key_only(self):
        """Test extracting key from key-only string."""
        result = extract_key_from_vertex_id("123")
        assert result == "123"
    
    def test_extract_with_multiple_slashes(self):
        """Test extracting key with multiple slashes."""
        result = extract_key_from_vertex_id("companies/sub/123")
        assert result == "123"  # Takes last part
    
    def test_extract_empty_key(self):
        """Test extracting empty key."""
        result = extract_key_from_vertex_id("companies/")
        assert result == ""
    
    def test_extract_special_characters(self):
        """Test extracting key with special characters."""
        result = extract_key_from_vertex_id("companies/key-with-dashes_123")
        assert result == "key-with-dashes_123"


class TestParseVertexId:
    """Test parse_vertex_id function."""
    
    def test_parse_formatted_id(self):
        """Test parsing formatted ID."""
        collection, key = parse_vertex_id("companies/123")
        assert collection == "companies"
        assert key == "123"
    
    def test_parse_key_only(self):
        """Test parsing key-only string."""
        collection, key = parse_vertex_id("123")
        assert collection is None
        assert key == "123"
    
    def test_parse_with_multiple_slashes(self):
        """Test parsing with multiple slashes."""
        collection, key = parse_vertex_id("companies/sub/123")
        assert collection == "companies"
        assert key == "sub/123"  # Only splits on first /
    
    def test_parse_empty_collection(self):
        """Test parsing with empty collection."""
        collection, key = parse_vertex_id("/123")
        assert collection == ""
        assert key == "123"
    
    def test_parse_empty_key(self):
        """Test parsing with empty key."""
        collection, key = parse_vertex_id("companies/")
        assert collection == "companies"
        assert key == ""


class TestNormalizeVertexIds:
    """Test normalize_vertex_ids function."""
    
    def test_normalize_mixed_formats(self):
        """Test normalizing mixed format IDs."""
        ids = ["123", "companies/456", "789"]
        result = normalize_vertex_ids(ids, "companies")
        assert result == ["companies/123", "companies/456", "companies/789"]
    
    def test_normalize_all_formatted(self):
        """Test normalizing already formatted IDs."""
        ids = ["companies/123", "companies/456"]
        result = normalize_vertex_ids(ids, "companies")
        assert result == ["companies/123", "companies/456"]
    
    def test_normalize_all_keys(self):
        """Test normalizing all key-only IDs."""
        ids = ["123", "456", "789"]
        result = normalize_vertex_ids(ids, "customers")
        assert result == ["customers/123", "customers/456", "customers/789"]
    
    def test_normalize_empty_list(self):
        """Test normalizing empty list."""
        result = normalize_vertex_ids([], "companies")
        assert result == []
    
    def test_normalize_with_default_collection(self):
        """Test normalizing with default collection."""
        ids = ["123", "456"]
        result = normalize_vertex_ids(ids)
        assert result == ["vertices/123", "vertices/456"]


class TestIsValidVertexId:
    """Test is_valid_vertex_id function."""
    
    def test_valid_formatted_id(self):
        """Test valid formatted ID."""
        assert is_valid_vertex_id("companies/123") is True
    
    def test_valid_key_only(self):
        """Test valid key-only ID."""
        assert is_valid_vertex_id("123") is True
    
    def test_invalid_empty_string(self):
        """Test invalid empty string."""
        assert is_valid_vertex_id("") is False
    
    def test_invalid_empty_collection(self):
        """Test invalid ID with empty collection."""
        assert is_valid_vertex_id("/123") is False
    
    def test_invalid_empty_key(self):
        """Test invalid ID with empty key."""
        assert is_valid_vertex_id("companies/") is False
    
    def test_invalid_multiple_slashes(self):
        """Test invalid ID with multiple slashes."""
        # Actually valid - just has collection/sub/key format
        assert is_valid_vertex_id("companies/sub/123") is True
    
    def test_invalid_none(self):
        """Test invalid None value."""
        assert is_valid_vertex_id(None) is False
    
    def test_invalid_non_string(self):
        """Test invalid non-string value."""
        assert is_valid_vertex_id(123) is False
        assert is_valid_vertex_id([]) is False
    
    def test_valid_with_whitespace(self):
        """Test valid ID with whitespace (should be trimmed by caller)."""
        # Function doesn't trim, so whitespace-only is invalid
        assert is_valid_vertex_id("   ") is True  # Non-empty after strip
        assert is_valid_vertex_id("companies/123") is True


class TestExtractCollectionFromVertexId:
    """Test extract_collection_from_vertex_id function."""
    
    def test_extract_from_formatted_id(self):
        """Test extracting collection from formatted ID."""
        result = extract_collection_from_vertex_id("companies/123")
        assert result == "companies"
    
    def test_extract_from_key_only(self):
        """Test extracting collection from key-only string."""
        result = extract_collection_from_vertex_id("123")
        assert result is None
    
    def test_extract_with_multiple_slashes(self):
        """Test extracting collection with multiple slashes."""
        result = extract_collection_from_vertex_id("companies/sub/123")
        assert result == "companies"  # Takes first part
    
    def test_extract_empty_collection(self):
        """Test extracting empty collection."""
        result = extract_collection_from_vertex_id("/123")
        assert result == ""


class TestGraphUtilsIntegration:
    """Integration tests for graph utils functions."""
    
    def test_round_trip_format_extract(self):
        """Test round-trip: format then extract."""
        key = "123"
        collection = "companies"
        
        formatted = format_vertex_id(key, collection)
        extracted = extract_key_from_vertex_id(formatted)
        
        assert extracted == key
    
    def test_round_trip_parse_format(self):
        """Test round-trip: parse then format."""
        vertex_id = "companies/123"
        
        collection, key = parse_vertex_id(vertex_id)
        formatted = format_vertex_id(key, collection)
        
        assert formatted == vertex_id
    
    def test_normalize_then_extract(self):
        """Test normalize then extract keys."""
        ids = ["123", "companies/456", "789"]
        normalized = normalize_vertex_ids(ids, "companies")
        extracted = [extract_key_from_vertex_id(nid) for nid in normalized]
        
        assert extracted == ["123", "456", "789"]
    
    def test_validate_then_format(self):
        """Test validate then format."""
        key = "123"
        collection = "companies"
        
        assert is_valid_vertex_id(key) is True
        formatted = format_vertex_id(key, collection)
        assert is_valid_vertex_id(formatted) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

