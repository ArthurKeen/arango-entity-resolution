"""
Tests for validation_utils module.
"""

import pytest
from unittest.mock import Mock, MagicMock

from entity_resolution.utils.validation_utils import validate_er_results


class TestValidateERResults:
    """Tests for validate_er_results function."""
    
    def test_validate_er_results_all_pass(self):
        """Test validation when all counts match."""
        db = Mock()
        
        # Mock collections with matching counts
        similar_to = Mock()
        similar_to.count.return_value = 100
        entity_clusters = Mock()
        entity_clusters.count.return_value = 50
        
        db.has_collection.side_effect = lambda name: True
        db.collection.side_effect = lambda name: {
            'similarTo': similar_to,
            'entity_clusters': entity_clusters
        }[name]
        
        results = {
            'edges_created': 100,
            'clusters_found': 50
        }
        
        validations = [
            {
                'collection': 'similarTo',
                'expected_key': 'edges_created',
                'description': 'Similarity edges'
            },
            {
                'collection': 'entity_clusters',
                'expected_key': 'clusters_found',
                'description': 'Entity clusters'
            }
        ]
        
        result = validate_er_results(db, results, validations)
        
        assert result['passed'] is True
        assert result['summary']['passed'] == 2
        assert result['summary']['failed'] == 0
        assert result['summary']['errors'] == 0
    
    def test_validate_er_results_count_mismatch(self):
        """Test validation when counts don't match."""
        db = Mock()
        
        similar_to = Mock()
        similar_to.count.return_value = 90  # Expected 100
        
        db.has_collection.return_value = True
        db.collection.return_value = similar_to
        
        results = {'edges_created': 100}
        
        validations = [
            {
                'collection': 'similarTo',
                'expected_key': 'edges_created',
                'description': 'Similarity edges'
            }
        ]
        
        result = validate_er_results(db, results, validations)
        
        assert result['passed'] is False
        assert result['summary']['failed'] == 1
        assert result['validations'][0]['status'] == 'fail'
        assert result['validations'][0]['expected'] == 100
        assert result['validations'][0]['actual'] == 90
    
    def test_validate_er_results_default_validations(self):
        """Test validation with default validation config."""
        db = Mock()
        
        similar_to = Mock()
        similar_to.count.return_value = 100
        entity_clusters = Mock()
        entity_clusters.count.return_value = 50
        address_same_as = Mock()
        address_same_as.count.return_value = 200
        
        db.has_collection.return_value = True
        def get_collection(name):
            return {
                'similarTo': similar_to,
                'entity_clusters': entity_clusters,
                'address_sameAs': address_same_as
            }[name]
        db.collection.side_effect = get_collection
        
        results = {
            'edges_created': 100,  # For similarTo
            'clusters_found': 50,  # For entity_clusters
            # address_sameAs also uses 'edges_created'
        }
        
        result = validate_er_results(db, results)
        
        assert result['summary']['total'] == 3
        # Note: address_sameAs will fail because results['edges_created'] is 100
        # but address_sameAs has 200 documents
    
    def test_validate_er_results_zero_expected(self):
        """Test validation when expected count is zero."""
        db = Mock()
        
        results = {'edges_created': 0}
        
        validations = [
            {
                'collection': 'similarTo',
                'expected_key': 'edges_created',
                'description': 'Similarity edges'
            }
        ]
        
        result = validate_er_results(db, results, validations)
        
        assert result['passed'] is True
        assert result['validations'][0]['status'] == 'pass'
        assert result['validations'][0]['expected'] == 0
        assert result['validations'][0]['actual'] == 0
    
    def test_validate_er_results_collection_not_exists(self):
        """Test validation when collection does not exist."""
        db = Mock()
        db.has_collection.return_value = False
        
        results = {'edges_created': 100}
        
        validations = [
            {
                'collection': 'missing_collection',
                'expected_key': 'edges_created',
                'description': 'Missing collection'
            }
        ]
        
        result = validate_er_results(db, results, validations)
        
        assert result['passed'] is False
        assert result['validations'][0]['status'] == 'fail'
        assert "does not exist" in result['validations'][0]['error']
    
    def test_validate_er_results_count_error(self):
        """Test validation when count operation fails."""
        db = Mock()
        
        error_collection = Mock()
        error_collection.count.side_effect = Exception("Count failed")
        
        db.has_collection.return_value = True
        db.collection.return_value = error_collection
        
        results = {'edges_created': 100}
        
        validations = [
            {
                'collection': 'error_collection',
                'expected_key': 'edges_created',
                'description': 'Error collection'
            }
        ]
        
        result = validate_er_results(db, results, validations)
        
        assert result['passed'] is False
        assert result['summary']['errors'] == 1
        assert result['validations'][0]['status'] == 'error'
        assert "Count failed" in result['validations'][0]['error']
    
    def test_validate_er_results_partial_success(self):
        """Test validation with mixed pass/fail results."""
        db = Mock()
        
        success_collection = Mock()
        success_collection.count.return_value = 100
        fail_collection = Mock()
        fail_collection.count.return_value = 50  # Expected 200
        
        db.has_collection.return_value = True
        def get_collection(name):
            return {
                'success_collection': success_collection,
                'fail_collection': fail_collection
            }[name]
        db.collection.side_effect = get_collection
        
        results = {
            'edges_created': 100,
            'clusters_found': 200
        }
        
        validations = [
            {
                'collection': 'success_collection',
                'expected_key': 'edges_created',
                'description': 'Success'
            },
            {
                'collection': 'fail_collection',
                'expected_key': 'clusters_found',
                'description': 'Fail'
            }
        ]
        
        result = validate_er_results(db, results, validations)
        
        assert result['passed'] is False
        assert result['summary']['passed'] == 1
        assert result['summary']['failed'] == 1

