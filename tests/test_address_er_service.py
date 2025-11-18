"""
Unit Tests for AddressERService

Comprehensive tests for the AddressERService component.
Note: Some tests require database connection (integration tests).
"""

import pytest
import sys
import os
import tempfile
import csv
from unittest.mock import Mock, MagicMock, patch, call

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.services.address_er_service import AddressERService


class TestAddressERService:
    """Test cases for AddressERService."""
    
    def test_initialization_defaults(self):
        """Test initialization with default parameters."""
        db_mock = Mock()
        
        service = AddressERService(
            db=db_mock,
            collection='addresses'
        )
        
        assert service.collection == 'addresses'
        assert service.edge_collection == 'address_sameAs'
        assert service.max_block_size == 100
        assert service.street_field == 'ADDRESS_LINE_1'
        assert service.city_field == 'PRIMARY_TOWN'
        assert service.state_field == 'TERRITORY_CODE'
    
    def test_initialization_custom_mapping(self):
        """Test initialization with custom field mapping."""
        db_mock = Mock()
        
        custom_mapping = {
            'street': 'STREET_ADDRESS',
            'city': 'CITY_NAME',
            'state': 'STATE_CODE',
            'postal_code': 'ZIP_CODE'
        }
        
        service = AddressERService(
            db=db_mock,
            collection='addresses',
            field_mapping=custom_mapping
        )
        
        assert service.street_field == 'STREET_ADDRESS'
        assert service.city_field == 'CITY_NAME'
        assert service.state_field == 'STATE_CODE'
        assert service.postal_code_field == 'ZIP_CODE'
    
    def test_initialization_custom_config(self):
        """Test initialization with custom configuration."""
        db_mock = Mock()
        
        config = {
            'max_block_size': 50,
            'min_bm25_score': 3.0,
            'batch_size': 1000
        }
        
        service = AddressERService(
            db=db_mock,
            collection='addresses',
            config=config
        )
        
        assert service.max_block_size == 50
        assert service.min_bm25_score == 3.0
        assert service.batch_size == 1000
    
    def test_setup_analyzers_creates_new(self):
        """Test analyzer setup creates new analyzers."""
        db_mock = Mock()
        db_mock.analyzers.return_value = []  # No existing analyzers
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        created = service._setup_analyzers()
        
        # Should create 2 analyzers
        assert len(created) == 2
        assert 'address_normalizer' in created
        assert 'text_normalizer' in created
        assert db_mock.create_analyzer.call_count == 2
    
    def test_setup_analyzers_skips_existing(self):
        """Test analyzer setup skips existing analyzers."""
        db_mock = Mock()
        db_mock.analyzers.return_value = [
            {'name': 'address_normalizer'},
            {'name': 'text_normalizer'}
        ]
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        created = service._setup_analyzers()
        
        # Should not create any (all exist)
        assert len(created) == 0
        assert db_mock.create_analyzer.call_count == 0
    
    def test_setup_search_view_creates_new(self):
        """Test search view setup creates new view."""
        db_mock = Mock()
        db_mock.views.return_value = []  # No existing views
        # Mock analyzers to return analyzers without prefix
        db_mock.analyzers.return_value = [
            {'name': 'address_normalizer'},
            {'name': 'text_normalizer'},
            {'name': 'text_en'},
            {'name': 'identity'}
        ]
        # Mock properties to return database info
        db_mock.properties.return_value = {'name': 'test_db'}
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        view_name = service._setup_search_view()
        
        assert view_name == 'addresses_search'
        assert db_mock.create_arangosearch_view.called
    
    def test_setup_search_view_replaces_existing(self):
        """Test search view setup replaces existing view."""
        db_mock = Mock()
        db_mock.views.return_value = [{'name': 'addresses_search'}]
        # Mock analyzers to return analyzers without prefix
        db_mock.analyzers.return_value = [
            {'name': 'address_normalizer'},
            {'name': 'text_normalizer'},
            {'name': 'text_en'},
            {'name': 'identity'}
        ]
        # Mock properties to return database info
        db_mock.properties.return_value = {'name': 'test_db'}
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        view_name = service._setup_search_view()
        
        assert view_name == 'addresses_search'
        assert db_mock.delete_view.called
        assert db_mock.create_arangosearch_view.called
    
    def test_resolve_analyzer_name_without_prefix(self):
        """Test analyzer name resolution when analyzer has no prefix."""
        db_mock = Mock()
        db_mock.analyzers.return_value = [
            {'name': 'address_normalizer'},
            {'name': 'text_normalizer'}
        ]
        db_mock.properties.return_value = {'name': 'test_db'}
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        resolved = service._resolve_analyzer_name('address_normalizer')
        assert resolved == 'address_normalizer'
    
    def test_resolve_analyzer_name_with_database_prefix(self):
        """Test analyzer name resolution when analyzer has database prefix."""
        db_mock = Mock()
        db_mock.analyzers.return_value = [
            {'name': 'test_db::address_normalizer'},
            {'name': 'test_db::text_normalizer'}
        ]
        db_mock.properties.return_value = {'name': 'test_db'}
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        resolved = service._resolve_analyzer_name('address_normalizer')
        assert resolved == 'test_db::address_normalizer'
    
    def test_resolve_analyzer_name_fallback_search(self):
        """Test analyzer name resolution fallback when database name unavailable."""
        db_mock = Mock()
        db_mock.analyzers.return_value = [
            {'name': 'some_db::address_normalizer'},
            {'name': 'other_db::text_normalizer'}
        ]
        # Mock properties to raise exception (simulating unavailable database name)
        db_mock.properties.side_effect = AttributeError("No properties")
        db_mock.name = None  # No name attribute
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        resolved = service._resolve_analyzer_name('address_normalizer')
        assert resolved == 'some_db::address_normalizer'
    
    def test_setup_search_view_uses_prefixed_analyzers(self):
        """Test that search view setup uses database-prefixed analyzers when present."""
        db_mock = Mock()
        db_mock.views.return_value = []
        # Mock analyzers with database prefix
        db_mock.analyzers.return_value = [
            {'name': 'my_db::address_normalizer'},
            {'name': 'my_db::text_normalizer'},
            {'name': 'text_en'},  # Built-in analyzer, no prefix
            {'name': 'identity'}  # Built-in analyzer, no prefix
        ]
        db_mock.properties.return_value = {'name': 'my_db'}
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        view_name = service._setup_search_view()
        
        assert view_name == 'addresses_search'
        assert db_mock.create_arangosearch_view.called
        
        # Verify that prefixed analyzer names were used
        call_args = db_mock.create_arangosearch_view.call_args
        # Handle both positional and keyword arguments
        if call_args.kwargs:
            view_properties = call_args.kwargs.get('properties', {})
        else:
            view_properties = call_args[1].get('properties', {})
        
        links = view_properties.get('links', {})
        addresses_config = links.get('addresses', {})
        fields = addresses_config.get('fields', {})
        street_analyzers = fields.get('ADDRESS_LINE_1', {}).get('analyzers', [])
        city_analyzers = fields.get('PRIMARY_TOWN', {}).get('analyzers', [])
        
        assert 'my_db::address_normalizer' in street_analyzers
        assert 'my_db::text_normalizer' in city_analyzers
    
    def test_find_duplicate_addresses_query_structure(self):
        """Test that find_duplicate_addresses generates correct query."""
        db_mock = Mock()
        cursor_mock = Mock()
        cursor_mock.__iter__ = Mock(return_value=iter([]))
        db_mock.aql.execute.return_value = cursor_mock
        
        service = AddressERService(
            db=db_mock,
            collection='test_addresses',
            field_mapping={
                'street': 'STREET',
                'city': 'CITY',
                'state': 'STATE',
                'postal_code': 'ZIP'
            }
        )
        
        blocks, total = service._find_duplicate_addresses(max_block_size=100)
        
        # Verify query was called
        assert db_mock.aql.execute.called
        
        # Get the query that was executed
        call_args = db_mock.aql.execute.call_args
        query = call_args[0][0] if call_args[0] else None
        
        # Verify query contains expected elements
        assert query is not None
        assert 'test_addresses' in query
        assert 'STREET' in query
        assert 'CITY' in query
        assert 'STATE' in query
        assert 'ZIP' in query
        assert 'max_block_size' in str(call_args[1]['bind_vars'])
    
    def test_find_duplicate_addresses_processes_results(self):
        """Test that find_duplicate_addresses processes results correctly."""
        db_mock = Mock()
        cursor_mock = Mock()
        
        # Mock results
        mock_results = [
            {
                'block_key': 'block1',
                'addresses': ['addr1', 'addr2', 'addr3'],
                'size': 3
            },
            {
                'block_key': 'block2',
                'addresses': ['addr4', 'addr5'],
                'size': 2
            }
        ]
        cursor_mock.__iter__ = Mock(return_value=iter(mock_results))
        db_mock.aql.execute.return_value = cursor_mock
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        blocks, total = service._find_duplicate_addresses(max_block_size=100)
        
        assert len(blocks) == 2
        assert 'block1' in blocks
        assert 'block2' in blocks
        assert blocks['block1'] == ['addr1', 'addr2', 'addr3']
        assert blocks['block2'] == ['addr4', 'addr5']
        assert total == 5  # 3 + 2
    
    def test_create_edges_creates_collection(self):
        """Test that create_edges creates collection if missing."""
        db_mock = Mock()
        db_mock.has_collection.return_value = False
        db_mock.collection.return_value = Mock()
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        blocks = {'block1': ['addr1', 'addr2']}
        edges_created = service._create_edges(blocks)
        
        assert db_mock.has_collection.called
        assert db_mock.create_collection.called
        assert edges_created == 1  # 2 addresses = 1 edge
    
    def test_create_edges_calculates_correct_count(self):
        """Test that create_edges calculates edge count correctly."""
        db_mock = Mock()
        db_mock.has_collection.return_value = True
        edge_collection_mock = Mock()
        db_mock.collection.return_value = edge_collection_mock
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        # Block with 3 addresses = 3 edges (3 choose 2)
        blocks = {'block1': ['addr1', 'addr2', 'addr3']}
        edges_created = service._create_edges(blocks)
        
        assert edges_created == 3
        assert edge_collection_mock.insert_many.called
    
    def test_create_edges_multiple_blocks(self):
        """Test edge creation with multiple blocks."""
        db_mock = Mock()
        db_mock.has_collection.return_value = True
        edge_collection_mock = Mock()
        db_mock.collection.return_value = edge_collection_mock
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        # Block 1: 2 addresses = 1 edge
        # Block 2: 3 addresses = 3 edges
        # Total: 4 edges
        blocks = {
            'block1': ['addr1', 'addr2'],
            'block2': ['addr3', 'addr4', 'addr5']
        }
        edges_created = service._create_edges(blocks)
        
        assert edges_created == 4
        assert edge_collection_mock.insert_many.call_count == 2
    
    @patch('entity_resolution.services.address_er_service.WCCClusteringService')
    def test_cluster_addresses_calls_clustering_service(self, mock_wcc_class):
        """Test that cluster_addresses calls WCCClusteringService."""
        db_mock = Mock()
        mock_wcc_instance = Mock()
        mock_wcc_instance.cluster.return_value = [['addr1', 'addr2'], ['addr3']]
        mock_wcc_class.return_value = mock_wcc_instance
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        clusters = service._cluster_addresses(min_cluster_size=2)
        
        assert mock_wcc_class.called
        assert mock_wcc_instance.cluster.called
        assert len(clusters) == 2
    
    @patch('entity_resolution.services.address_er_service.time.sleep')
    def test_setup_infrastructure_complete(self, mock_sleep):
        """Test complete infrastructure setup."""
        db_mock = Mock()
        db_mock.analyzers.return_value = []
        db_mock.views.return_value = []
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        results = service.setup_infrastructure()
        
        assert 'analyzers_created' in results
        assert 'view_created' in results
        assert 'view_build_wait_seconds' in results
        assert mock_sleep.called
    
    def test_run_pipeline_without_clustering(self):
        """Test running complete pipeline without clustering."""
        db_mock = Mock()
        
        # Mock find_duplicate_addresses
        cursor_mock = Mock()
        cursor_mock.__iter__ = Mock(return_value=iter([
            {'block_key': 'block1', 'addresses': ['addr1', 'addr2'], 'size': 2}
        ]))
        db_mock.aql.execute.return_value = cursor_mock
        db_mock.has_collection.return_value = True
        edge_collection_mock = Mock()
        db_mock.collection.return_value = edge_collection_mock
        
        service = AddressERService(db=db_mock, collection='addresses')
        
        results = service.run(create_edges=True, cluster=False)
        
        assert 'blocks_found' in results
        assert 'addresses_matched' in results
        assert 'edges_created' in results
        assert 'clusters_found' in results
        assert results['clusters_found'] is None
        assert 'runtime_seconds' in results
    
    def test_repr(self):
        """Test string representation."""
        db_mock = Mock()
        service = AddressERService(
            db=db_mock,
            collection='test_addresses',
            edge_collection='test_edges'
        )
        
        repr_str = repr(service)
        assert 'AddressERService' in repr_str
        assert 'test_addresses' in repr_str
        assert 'test_edges' in repr_str
    
    def test_create_edges_optimized_batching(self):
        """Test that optimized batching batches across blocks."""
        db_mock = Mock()
        db_mock.has_collection.return_value = True
        edge_collection_mock = Mock()
        db_mock.collection.return_value = edge_collection_mock
        
        service = AddressERService(
            db=db_mock, 
            collection='addresses',
            config={'edge_loading_method': 'api', 'edge_batch_size': 5}
        )
        
        # Create blocks that will generate more than batch_size edges
        blocks = {
            'block1': ['addr1', 'addr2', 'addr3'],  # 3 edges
            'block2': ['addr4', 'addr5', 'addr6']   # 3 edges
        }
        
        edges_created = service._create_edges(blocks)
        
        # Should batch across blocks (6 edges total, batch_size=5, so 2 batches)
        assert edge_collection_mock.insert_many.call_count == 2
        assert edges_created == 6
    
    @patch('subprocess.run')
    @patch('tempfile.mktemp')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_create_edges_via_csv_success(self, mock_remove, mock_exists, mock_mktemp, mock_subprocess):
        """Test CSV-based edge creation with successful arangoimport."""
        db_mock = Mock()
        db_mock.has_collection.return_value = True
        db_mock.name = 'test_db'
        db_mock.connection = Mock()
        db_mock.connection.host = 'localhost'
        db_mock.connection.port = 8529
        db_mock.connection.username = 'root'
        db_mock.connection.password = 'test'
        
        # Mock subprocess result
        mock_result = Mock()
        mock_result.stdout = "created: 6"
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        # Mock tempfile
        mock_mktemp.return_value = '/tmp/test_edges.csv'
        mock_exists.return_value = True
        
        service = AddressERService(
            db=db_mock,
            collection='addresses',
            config={'edge_loading_method': 'csv'}
        )
        
        blocks = {
            'block1': ['addr1', 'addr2', 'addr3'],  # 3 edges
            'block2': ['addr4', 'addr5']            # 1 edge
        }
        
        edges_created = service._create_edges_via_csv(blocks)
        
        assert edges_created == 6
        assert mock_subprocess.called
        # Verify arangoimport was called with correct arguments
        call_args = mock_subprocess.call_args
        assert 'arangoimport' in call_args[0][0]
        assert 'test_db' in call_args[0][0]
    
    @patch('subprocess.run')
    def test_create_edges_via_csv_fallback_on_file_not_found(self, mock_subprocess):
        """Test that CSV method falls back to API method if arangoimport not found."""
        db_mock = Mock()
        db_mock.has_collection.return_value = True
        db_mock.name = 'test_db'
        
        # Simulate FileNotFoundError
        mock_subprocess.side_effect = FileNotFoundError("arangoimport not found")
        
        service = AddressERService(
            db=db_mock,
            collection='addresses',
            config={'edge_loading_method': 'csv'}
        )
        
        blocks = {
            'block1': ['addr1', 'addr2']
        }
        
        # Should fall back to API method
        edge_collection_mock = Mock()
        db_mock.collection.return_value = edge_collection_mock
        
        edges_created = service._create_edges_via_csv(blocks)
        
        # Should have used API method (insert_many called)
        assert edge_collection_mock.insert_many.called
    
    def test_run_with_csv_method(self):
        """Test run() method with CSV edge loading."""
        db_mock = Mock()
        
        # Mock find_duplicate_addresses
        cursor_mock = Mock()
        cursor_mock.__iter__ = Mock(return_value=iter([
            {'block_key': 'block1', 'addresses': ['addr1', 'addr2'], 'size': 2}
        ]))
        db_mock.aql.execute.return_value = cursor_mock
        db_mock.has_collection.return_value = True
        
        # Mock CSV method
        with patch.object(AddressERService, '_create_edges_via_csv', return_value=1) as mock_csv:
            service = AddressERService(
                db=db_mock,
                collection='addresses',
                config={'edge_loading_method': 'csv'}
            )
            
            results = service.run(create_edges=True, cluster=False)
            
            assert mock_csv.called
            assert results['edges_created'] == 1
    
    def test_run_with_api_method(self):
        """Test run() method with API edge loading (default)."""
        db_mock = Mock()
        
        # Mock find_duplicate_addresses
        cursor_mock = Mock()
        cursor_mock.__iter__ = Mock(return_value=iter([
            {'block_key': 'block1', 'addresses': ['addr1', 'addr2'], 'size': 2}
        ]))
        db_mock.aql.execute.return_value = cursor_mock
        db_mock.has_collection.return_value = True
        edge_collection_mock = Mock()
        db_mock.collection.return_value = edge_collection_mock
        
        service = AddressERService(
            db=db_mock,
            collection='addresses',
            config={'edge_loading_method': 'api'}
        )
        
        results = service.run(create_edges=True, cluster=False)
        
        assert edge_collection_mock.insert_many.called
        assert 'edges_created' in results


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

