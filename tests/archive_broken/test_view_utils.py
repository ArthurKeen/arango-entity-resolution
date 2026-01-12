"""
Tests for view_utils module.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from arango.exceptions import ViewGetError

from entity_resolution.utils.view_utils import (
    resolve_analyzer_name,
    verify_view_analyzers,
    fix_view_analyzer_names,
    verify_and_fix_view_analyzers
)


class TestResolveAnalyzerName:
    """Tests for resolve_analyzer_name function."""
    
    def test_resolve_analyzer_name_without_prefix(self):
        """Test resolving analyzer name when it exists without prefix."""
        db = Mock()
        db.analyzers.return_value = [
            {'name': 'address_normalizer'},
            {'name': 'text_normalizer'}
        ]
        
        result = resolve_analyzer_name(db, 'address_normalizer')
        assert result == 'address_normalizer'
    
    def test_resolve_analyzer_name_with_database_prefix(self):
        """Test resolving analyzer name when it exists with database prefix."""
        db = Mock()
        db.analyzers.return_value = [
            {'name': 'my_db::address_normalizer'},
            {'name': 'my_db::text_normalizer'}
        ]
        db.properties.return_value = {'name': 'my_db'}
        
        result = resolve_analyzer_name(db, 'address_normalizer')
        assert result == 'my_db::address_normalizer'
    
    def test_resolve_analyzer_name_fallback_search(self):
        """Test fallback search when database name unavailable."""
        db = Mock()
        db.analyzers.return_value = [
            {'name': 'other_db::address_normalizer'},
            {'name': 'my_db::text_normalizer'}
        ]
        db.properties.side_effect = AttributeError("No properties")
        db.name = None
        
        result = resolve_analyzer_name(db, 'address_normalizer')
        assert result == 'other_db::address_normalizer'
    
    def test_resolve_analyzer_name_builtin_analyzer(self):
        """Test resolving built-in analyzer (text_en, identity)."""
        db = Mock()
        db.analyzers.return_value = [
            {'name': 'text_en'},
            {'name': 'identity'}
        ]
        
        result = resolve_analyzer_name(db, 'text_en')
        assert result == 'text_en'
    
    def test_resolve_analyzer_name_not_found(self):
        """Test resolving analyzer name that doesn't exist."""
        db = Mock()
        db.analyzers.return_value = [
            {'name': 'other_analyzer'}
        ]
        db.properties.side_effect = AttributeError("No properties")
        db.name = None
        
        # Should return original name (will fail later in view creation)
        result = resolve_analyzer_name(db, 'missing_analyzer')
        assert result == 'missing_analyzer'


class TestVerifyViewAnalyzers:
    """Tests for verify_view_analyzers function."""
    
    def test_verify_view_analyzers_view_exists_and_accessible(self):
        """Test verification when view exists and is accessible."""
        db = Mock()
        db.views.return_value = [{'name': 'test_view'}]
        db.aql.execute.return_value = [1]
        
        is_accessible, error = verify_view_analyzers(db, 'test_view', 'test_collection')
        
        assert is_accessible is True
        assert error is None
        db.aql.execute.assert_called_once()
    
    def test_verify_view_analyzers_view_not_exists(self):
        """Test verification when view does not exist."""
        db = Mock()
        db.views.return_value = [{'name': 'other_view'}]
        
        is_accessible, error = verify_view_analyzers(db, 'test_view', 'test_collection')
        
        assert is_accessible is False
        assert "does not exist" in error
    
    def test_verify_view_analyzers_analyzer_error(self):
        """Test verification when view has analyzer configuration issues."""
        db = Mock()
        db.views.return_value = [{'name': 'test_view'}]
        db.aql.execute.side_effect = Exception("failed to build scorers")
        
        is_accessible, error = verify_view_analyzers(db, 'test_view', 'test_collection')
        
        assert is_accessible is False
        assert "Analyzer configuration issue" in error
    
    def test_verify_view_analyzers_custom_test_query(self):
        """Test verification with custom test query."""
        db = Mock()
        db.views.return_value = [{'name': 'test_view'}]
        db.aql.execute.return_value = []
        
        custom_query = "FOR doc IN test_view SEARCH doc.field == 'test' LIMIT 1 RETURN doc"
        is_accessible, error = verify_view_analyzers(
            db, 'test_view', 'test_collection', test_query=custom_query
        )
        
        assert is_accessible is True
        db.aql.execute.assert_called_once_with(custom_query)


class TestFixViewAnalyzerNames:
    """Tests for fix_view_analyzer_names function."""
    
    @patch('entity_resolution.utils.view_utils.resolve_analyzer_name')
    @patch('time.sleep')
    def test_fix_view_analyzer_names_success(self, mock_sleep, mock_resolve):
        """Test successfully fixing view analyzer names."""
        db = Mock()
        db.views.return_value = [{'name': 'test_view'}]
        db.has_view.return_value = True
        mock_resolve.side_effect = lambda db, name: f'resolved_{name}'
        
        field_analyzers = {
            'field1': ['analyzer1', 'analyzer2'],
            'field2': ['analyzer3']
        }
        
        result = fix_view_analyzer_names(
            db, 'test_view', 'test_collection', field_analyzers
        )
        
        assert result['view_created'] is True
        assert result['view_name'] == 'test_view'
        assert 'field1' in result['analyzers_resolved']
        assert db.delete_view.called
        assert db.create_arangosearch_view.called
    
    @patch('entity_resolution.utils.view_utils.resolve_analyzer_name')
    def test_fix_view_analyzer_names_resolves_analyzers(self, mock_resolve):
        """Test that analyzer names are properly resolved."""
        db = Mock()
        db.views.return_value = []
        mock_resolve.side_effect = lambda db, name: f'resolved_{name}'
        
        field_analyzers = {
            'field1': ['analyzer1']
        }
        
        result = fix_view_analyzer_names(
            db, 'test_view', 'test_collection', field_analyzers
        )
        
        assert result['analyzers_resolved']['field1'] == ['resolved_analyzer1']
        mock_resolve.assert_called()
    
    @patch('entity_resolution.utils.view_utils.resolve_analyzer_name')
    def test_fix_view_analyzer_names_handles_delete_error(self, mock_resolve):
        """Test handling error when deleting existing view."""
        db = Mock()
        db.views.return_value = [{'name': 'test_view'}]
        db.delete_view.side_effect = Exception("Delete failed")
        mock_resolve.side_effect = lambda db, name: name
        
        field_analyzers = {'field1': ['analyzer1']}
        
        # Should continue and try to create view anyway
        result = fix_view_analyzer_names(
            db, 'test_view', 'test_collection', field_analyzers
        )
        
        # View creation should still be attempted
        assert db.create_arangosearch_view.called
    
    @patch('entity_resolution.utils.view_utils.resolve_analyzer_name')
    def test_fix_view_analyzer_names_handles_create_error(self, mock_resolve):
        """Test handling error when creating view."""
        db = Mock()
        db.views.return_value = []
        db.create_arangosearch_view.side_effect = Exception("Create failed")
        mock_resolve.side_effect = lambda db, name: name
        
        field_analyzers = {'field1': ['analyzer1']}
        
        result = fix_view_analyzer_names(
            db, 'test_view', 'test_collection', field_analyzers
        )
        
        assert result['view_created'] is False
        assert result['error'] is not None
        assert "Create failed" in result['error']


class TestVerifyAndFixViewAnalyzers:
    """Tests for verify_and_fix_view_analyzers function."""
    
    @patch('entity_resolution.utils.view_utils.fix_view_analyzer_names')
    @patch('entity_resolution.utils.view_utils.verify_view_analyzers')
    def test_verify_and_fix_view_accessible(self, mock_verify, mock_fix):
        """Test when view is already accessible."""
        mock_verify.return_value = (True, None)
        
        db = Mock()
        field_analyzers = {'field1': ['analyzer1']}
        
        result = verify_and_fix_view_analyzers(
            db, 'test_view', 'test_collection', field_analyzers
        )
        
        assert result['verified'] is True
        assert result['fixed'] is False
        assert mock_fix.called is False
    
    @patch('entity_resolution.utils.view_utils.fix_view_analyzer_names')
    @patch('entity_resolution.utils.view_utils.verify_view_analyzers')
    def test_verify_and_fix_auto_fixes(self, mock_verify, mock_fix):
        """Test automatic fixing when view has analyzer issues."""
        mock_verify.return_value = (False, "Analyzer configuration issue")
        mock_fix.return_value = {
            'view_created': True,
            'view_name': 'test_view',
            'analyzers_resolved': {},
            'wait_seconds': 10,
            'error': None
        }
        # Second verification after fix succeeds
        mock_verify.side_effect = [
            (False, "Analyzer configuration issue"),  # First call
            (True, None)  # Second call after fix
        ]
        
        db = Mock()
        field_analyzers = {'field1': ['analyzer1']}
        
        result = verify_and_fix_view_analyzers(
            db, 'test_view', 'test_collection', field_analyzers, auto_fix=True
        )
        
        assert result['verified'] is True
        assert result['fixed'] is True
        assert mock_fix.called is True
    
    @patch('entity_resolution.utils.view_utils.fix_view_analyzer_names')
    @patch('entity_resolution.utils.view_utils.verify_view_analyzers')
    def test_verify_and_fix_no_auto_fix(self, mock_verify, mock_fix):
        """Test when auto_fix is disabled."""
        mock_verify.return_value = (False, "Analyzer configuration issue")
        
        db = Mock()
        field_analyzers = {'field1': ['analyzer1']}
        
        result = verify_and_fix_view_analyzers(
            db, 'test_view', 'test_collection', field_analyzers, auto_fix=False
        )
        
        assert result['verified'] is False
        assert result['fixed'] is False
        assert mock_fix.called is False

