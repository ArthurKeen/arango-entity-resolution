"""
Tests for pipeline_utils module.
"""

import pytest
from unittest.mock import Mock, MagicMock

from entity_resolution.utils.pipeline_utils import clean_er_results


class TestCleanERResults:
    """Tests for clean_er_results function."""
    
    def test_clean_er_results_default_collections(self):
        """Test cleaning with default collections."""
        db = Mock()
        
        # Mock collections with documents
        similar_to = Mock()
        similar_to.count.return_value = 100
        entity_clusters = Mock()
        entity_clusters.count.return_value = 50
        address_same_as = Mock()
        address_same_as.count.return_value = 200
        
        db.has_collection.side_effect = lambda name: True
        db.collection.side_effect = lambda name: {
            'similarTo': similar_to,
            'entity_clusters': entity_clusters,
            'address_sameAs': address_same_as
        }[name]
        
        result = clean_er_results(db)
        
        assert len(result['collections_cleaned']) == 3
        assert result['removed_counts']['similarTo'] == 100
        assert result['removed_counts']['entity_clusters'] == 50
        assert result['removed_counts']['address_sameAs'] == 200
        assert result['total_removed'] == 350
        assert len(result['errors']) == 0
    
    def test_clean_er_results_custom_collections(self):
        """Test cleaning with custom collection list."""
        db = Mock()
        
        custom_collection = Mock()
        custom_collection.count.return_value = 75
        
        db.has_collection.return_value = True
        db.collection.return_value = custom_collection
        
        result = clean_er_results(db, collections=['custom_collection'])
        
        assert len(result['collections_cleaned']) == 1
        assert result['removed_counts']['custom_collection'] == 75
        assert result['total_removed'] == 75
    
    def test_clean_er_results_empty_collections(self):
        """Test cleaning when collections are already empty."""
        db = Mock()
        
        empty_collection = Mock()
        empty_collection.count.return_value = 0
        
        db.has_collection.return_value = True
        db.collection.return_value = empty_collection
        
        result = clean_er_results(db, collections=['empty_collection'])
        
        assert len(result['collections_cleaned']) == 0
        assert result['total_removed'] == 0
    
    def test_clean_er_results_missing_collection(self):
        """Test handling when collection does not exist."""
        db = Mock()
        db.has_collection.return_value = False
        
        result = clean_er_results(db, collections=['missing_collection'])
        
        assert len(result['collections_cleaned']) == 0
        assert len(result['errors']) == 0  # Missing collections are not errors
    
    def test_clean_er_results_handles_truncate_error(self):
        """Test handling error during truncate operation."""
        db = Mock()
        
        error_collection = Mock()
        error_collection.count.return_value = 100
        error_collection.truncate.side_effect = Exception("Truncate failed")
        
        db.has_collection.return_value = True
        db.collection.return_value = error_collection
        
        result = clean_er_results(db, collections=['error_collection'])
        
        assert len(result['collections_cleaned']) == 0
        assert len(result['errors']) == 1
        assert result['errors'][0]['collection'] == 'error_collection'
        assert "Truncate failed" in result['errors'][0]['error']
    
    def test_clean_er_results_handles_count_error(self):
        """Test handling error during count operation."""
        db = Mock()
        
        error_collection = Mock()
        error_collection.count.side_effect = Exception("Count failed")
        
        db.has_collection.return_value = True
        db.collection.return_value = error_collection
        
        result = clean_er_results(db, collections=['error_collection'])
        
        assert len(result['collections_cleaned']) == 0
        assert len(result['errors']) == 1
        assert "Count failed" in result['errors'][0]['error']
    
    def test_clean_er_results_partial_success(self):
        """Test partial success when some collections fail."""
        db = Mock()
        
        # Successful collection
        success_collection = Mock()
        success_collection.count.return_value = 50
        
        # Failing collection
        error_collection = Mock()
        error_collection.count.side_effect = Exception("Count failed")
        
        def get_collection(name):
            if name == 'success_collection':
                return success_collection
            return error_collection
        
        db.has_collection.return_value = True
        db.collection.side_effect = get_collection
        
        result = clean_er_results(
            db, collections=['success_collection', 'error_collection']
        )
        
        assert len(result['collections_cleaned']) == 1
        assert result['removed_counts']['success_collection'] == 50
        assert len(result['errors']) == 1
        assert result['total_removed'] == 50

