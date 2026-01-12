"""
Unit tests for EmbeddingService

Tests embedding generation, batch processing, storage, and retrieval functionality.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch, call
from typing import List, Dict, Any

# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from entity_resolution.services.embedding_service import EmbeddingService, SENTENCE_TRANSFORMERS_AVAILABLE


class TestEmbeddingServiceInit:
    """Test EmbeddingService initialization"""
    
    def test_init_default_params(self):
        """Test initialization with default parameters"""
        service = EmbeddingService()
        
        assert service.model_name == 'all-MiniLM-L6-v2'
        assert service.device == 'cpu'
        assert service.embedding_field == 'embedding_vector'
        assert service._model is None  # Lazy loaded
    
    def test_init_custom_params(self):
        """Test initialization with custom parameters"""
        service = EmbeddingService(
            model_name='all-mpnet-base-v2',
            device='cuda',
            embedding_field='custom_embedding'
        )
        
        assert service.model_name == 'all-mpnet-base-v2'
        assert service.device == 'cuda'
        assert service.embedding_field == 'custom_embedding'
    
    def test_init_unsupported_model_warning(self):
        """Test warning for unsupported model name"""
        with patch('logging.warning') as mock_warning:
            service = EmbeddingService(model_name='unknown-model')
            mock_warning.assert_called()
            assert 'unknown-model' in str(mock_warning.call_args)
    
    def test_lazy_model_loading(self):
        """Test that model is not loaded until first use"""
        service = EmbeddingService()
        assert service._model is None
        
        # Access model property to trigger loading
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model
            
            _ = service.model
            
            assert service._model is not None
            mock_st.assert_called_once_with('all-MiniLM-L6-v2', device='cpu')


class TestRecordToText:
    """Test _record_to_text method"""
    
    def test_record_to_text_all_fields(self):
        """Test converting record to text with all fields"""
        service = EmbeddingService()
        
        record = {
            'name': 'John Smith',
            'company': 'Acme Corp',
            'email': 'john@acme.com'
        }
        
        text = service._record_to_text(record)
        
        assert 'John Smith' in text
        assert 'Acme Corp' in text
        assert 'john@acme.com' in text
    
    def test_record_to_text_specific_fields(self):
        """Test converting record to text with specific fields only"""
        service = EmbeddingService()
        
        record = {
            'name': 'John Smith',
            'company': 'Acme Corp',
            'email': 'john@acme.com',
            'phone': '555-1234'
        }
        
        text = service._record_to_text(record, text_fields=['name', 'company'])
        
        assert 'John Smith' in text
        assert 'Acme Corp' in text
        assert 'john@acme.com' not in text
        assert '555-1234' not in text
    
    def test_record_to_text_missing_fields(self):
        """Test handling of missing fields"""
        service = EmbeddingService()
        
        record = {
            'name': 'John Smith'
        }
        
        # Should not raise error
        text = service._record_to_text(record, text_fields=['name', 'company'])
        assert 'John Smith' in text
    
    def test_record_to_text_excludes_metadata(self):
        """Test that metadata fields are excluded"""
        service = EmbeddingService()
        
        record = {
            '_key': 'doc123',
            '_id': 'collection/doc123',
            'name': 'John Smith',
            'embedding_vector': [0.1, 0.2],
            'embedding_metadata': {'model': 'test'}
        }
        
        text = service._record_to_text(record)
        
        assert 'John Smith' in text
        assert 'doc123' not in text
        assert 'embedding_vector' not in text
    
    def test_record_to_text_empty_fields(self):
        """Test handling of empty field values"""
        service = EmbeddingService()
        
        record = {
            'name': '',
            'company': '   ',
            'email': 'john@acme.com'
        }
        
        text = service._record_to_text(record)
        
        # Empty/whitespace fields should be filtered out
        assert 'john@acme.com' in text
        # Empty strings should not create extra commas
        assert ',,' not in text


class TestGenerateEmbedding:
    """Test generate_embedding method"""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_generate_embedding_single_record(self, mock_st_class):
        """Test generating embedding for a single record"""
        # Setup mock
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_embedding = np.array([0.1, 0.2, 0.3])
        mock_model.encode.return_value = mock_embedding
        mock_st_class.return_value = mock_model
        
        service = EmbeddingService()
        record = {'name': 'John Smith', 'company': 'Acme'}
        
        embedding = service.generate_embedding(record)
        
        assert isinstance(embedding, np.ndarray)
        np.testing.assert_array_equal(embedding, mock_embedding)
        mock_model.encode.assert_called_once()
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_generate_embedding_custom_fields(self, mock_st_class):
        """Test generating embedding with custom text fields"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([0.1, 0.2])
        mock_st_class.return_value = mock_model
        
        service = EmbeddingService()
        record = {
            'name': 'John Smith',
            'company': 'Acme',
            'extra': 'ignored'
        }
        
        embedding = service.generate_embedding(record, text_fields=['name', 'company'])
        
        # Check that encode was called with text containing only specified fields
        call_args = mock_model.encode.call_args[0][0]
        assert 'John Smith' in call_args
        assert 'Acme' in call_args
        assert 'ignored' not in call_args


class TestGenerateEmbeddingsBatch:
    """Test generate_embeddings_batch method"""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_batch_generation(self, mock_st_class):
        """Test batch embedding generation"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_embeddings = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        mock_model.encode.return_value = mock_embeddings
        mock_st_class.return_value = mock_model
        
        service = EmbeddingService()
        records = [
            {'name': 'John Smith'},
            {'name': 'Jane Doe'},
            {'name': 'Bob Johnson'}
        ]
        
        embeddings = service.generate_embeddings_batch(records)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 2)
        np.testing.assert_array_equal(embeddings, mock_embeddings)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_batch_generation_empty_list(self, mock_st_class):
        """Test batch generation with empty list"""
        service = EmbeddingService()
        
        embeddings = service.generate_embeddings_batch([])
        
        assert isinstance(embeddings, np.ndarray)
        assert len(embeddings) == 0
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_batch_generation_custom_batch_size(self, mock_st_class):
        """Test batch generation with custom batch size"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1], [0.2]])
        mock_st_class.return_value = mock_model
        
        service = EmbeddingService()
        records = [{'name': 'A'}, {'name': 'B'}]
        
        service.generate_embeddings_batch(records, batch_size=16)
        
        # Check batch_size parameter was passed
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs['batch_size'] == 16
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_batch_generation_progress_bar(self, mock_st_class):
        """Test batch generation with progress bar"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1]])
        mock_st_class.return_value = mock_model
        
        service = EmbeddingService()
        records = [{'name': 'Test'}]
        
        service.generate_embeddings_batch(records, show_progress=True)
        
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs['show_progress_bar'] is True


class TestStoreEmbeddings:
    """Test store_embeddings method"""
    
    def test_store_embeddings_success(self):
        """Test successful embedding storage"""
        # Setup mock database
        mock_collection = Mock()
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        records = [
            {'_key': 'doc1'},
            {'_key': 'doc2'}
        ]
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        result = service.store_embeddings('test_collection', records, embeddings)
        
        assert result['updated'] == 2
        assert result['failed'] == 0
        assert result['total'] == 2
        assert mock_collection.update.call_count == 2
    
    def test_store_embeddings_length_mismatch(self):
        """Test error when records and embeddings have different lengths"""
        service = EmbeddingService()
        
        records = [{'_key': 'doc1'}]
        embeddings = np.array([[0.1], [0.2]])  # 2 embeddings, 1 record
        
        with pytest.raises(ValueError, match="must match"):
            service.store_embeddings('test', records, embeddings)
    
    def test_store_embeddings_missing_key(self):
        """Test error when record is missing _key field"""
        mock_db_manager = Mock()
        service = EmbeddingService(db_manager=mock_db_manager)
        
        records = [{'name': 'Test'}]  # Missing _key
        embeddings = np.array([[0.1]])
        
        with pytest.raises(ValueError, match="_key"):
            service.store_embeddings('test', records, embeddings)
    
    def test_store_embeddings_partial_failure(self):
        """Test handling of partial failures during storage"""
        # Setup mock that fails on second update
        mock_collection = Mock()
        mock_collection.update.side_effect = [None, Exception("Update failed")]
        
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        records = [{'_key': 'doc1'}, {'_key': 'doc2'}]
        embeddings = np.array([[0.1], [0.2]])
        
        result = service.store_embeddings('test', records, embeddings)
        
        assert result['updated'] == 1
        assert result['failed'] == 1
        assert result['total'] == 2
    
    def test_store_embeddings_includes_metadata(self):
        """Test that stored embeddings include metadata"""
        mock_collection = Mock()
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(
            model_name='all-MiniLM-L6-v2',
            db_manager=mock_db_manager
        )
        service._embedding_dim = 384
        
        records = [{'_key': 'doc1'}]
        embeddings = np.array([[0.1, 0.2, 0.3]])
        
        service.store_embeddings('test', records, embeddings)
        
        # Check the update call includes metadata
        update_data = mock_collection.update.call_args[0][0]
        assert 'embedding_metadata' in update_data
        assert update_data['embedding_metadata']['model'] == 'all-MiniLM-L6-v2'
        assert update_data['embedding_metadata']['dim'] == 384
        assert 'timestamp' in update_data['embedding_metadata']


class TestEnsureEmbeddingsExist:
    """Test ensure_embeddings_exist method"""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_all_embeddings_exist(self, mock_st_class):
        """Test when all documents already have embeddings"""
        # Setup mock database with no documents missing embeddings
        mock_cursor = []
        mock_aql = Mock()
        mock_aql.execute.return_value = mock_cursor
        
        mock_collection = Mock()
        mock_collection.count.return_value = 10
        
        mock_db = Mock()
        mock_db.aql = mock_aql
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        result = service.ensure_embeddings_exist(
            'test_collection',
            text_fields=['name']
        )
        
        assert result['generated'] == 0
        assert result['updated'] == 0
        assert result['total_docs'] == 10
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_generate_missing_embeddings(self, mock_st_class):
        """Test generating embeddings for documents that don't have them"""
        # Setup mock model
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1, 0.2]])
        mock_st_class.return_value = mock_model
        
        # Setup mock database with one document missing embedding
        mock_cursor = [{'_key': 'doc1', 'name': 'Test'}]
        mock_aql = Mock()
        mock_aql.execute.return_value = mock_cursor
        
        mock_collection = Mock()
        mock_collection.count.return_value = 5
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.aql = mock_aql
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        result = service.ensure_embeddings_exist(
            'test_collection',
            text_fields=['name']
        )
        
        assert result['generated'] == 1
        assert result['updated'] == 1
        assert result['failed'] == 0
        assert result['total_docs'] == 5
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_force_regenerate(self, mock_st_class):
        """Test force regenerating all embeddings"""
        # Setup mock
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1]])
        mock_st_class.return_value = mock_model
        
        mock_cursor = [{'_key': 'doc1', 'name': 'Test', 'embedding_vector': [0.5]}]
        mock_aql = Mock()
        mock_aql.execute.return_value = mock_cursor
        
        mock_collection = Mock()
        mock_collection.count.return_value = 1
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.aql = mock_aql
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        result = service.ensure_embeddings_exist(
            'test_collection',
            text_fields=['name'],
            force_regenerate=True
        )
        
        assert result['generated'] == 1  # Regenerated even though embedding existed


class TestGetEmbeddingStats:
    """Test get_embedding_stats method"""
    
    def test_get_stats_all_have_embeddings(self):
        """Test getting stats when all documents have embeddings"""
        # Setup mock database
        mock_aql = Mock()
        mock_aql.execute.side_effect = [
            [10],  # total count
            [10],  # with embeddings count
            [{'model': 'all-MiniLM-L6-v2', 'dim': 384}]  # sample metadata
        ]
        
        mock_db = Mock()
        mock_db.aql = mock_aql
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        stats = service.get_embedding_stats('test_collection')
        
        assert stats['collection'] == 'test_collection'
        assert stats['total_documents'] == 10
        assert stats['with_embeddings'] == 10
        assert stats['without_embeddings'] == 0
        assert stats['coverage_percent'] == 100.0
    
    def test_get_stats_partial_coverage(self):
        """Test getting stats with partial embedding coverage"""
        mock_aql = Mock()
        mock_aql.execute.side_effect = [
            [100],  # total
            [75],   # with embeddings
            []      # no sample (empty cursor)
        ]
        
        mock_db = Mock()
        mock_db.aql = mock_aql
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        stats = service.get_embedding_stats('test_collection')
        
        assert stats['total_documents'] == 100
        assert stats['with_embeddings'] == 75
        assert stats['without_embeddings'] == 25
        assert stats['coverage_percent'] == 75.0
        assert stats['sample_metadata'] is None
    
    def test_get_stats_empty_collection(self):
        """Test getting stats for empty collection"""
        mock_aql = Mock()
        mock_aql.execute.side_effect = [
            [0],  # total
            [0],  # with embeddings
            []    # no sample
        ]
        
        mock_db = Mock()
        mock_db.aql = mock_aql
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        
        stats = service.get_embedding_stats('test_collection')
        
        assert stats['total_documents'] == 0
        assert stats['coverage_percent'] == 0


class TestEmbeddingServiceProperties:
    """Test EmbeddingService properties and helpers"""
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embedding_dim_property(self, mock_st_class):
        """Test embedding_dim property"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_st_class.return_value = mock_model
        
        service = EmbeddingService(model_name='all-mpnet-base-v2')
        
        dim = service.embedding_dim
        
        assert dim == 768
        assert service._embedding_dim == 768
    
    def test_supported_models_constant(self):
        """Test that SUPPORTED_MODELS contains expected models"""
        assert 'all-MiniLM-L6-v2' in EmbeddingService.SUPPORTED_MODELS
        assert 'all-mpnet-base-v2' in EmbeddingService.SUPPORTED_MODELS
        
        # Check structure
        model_info = EmbeddingService.SUPPORTED_MODELS['all-MiniLM-L6-v2']
        assert 'dim' in model_info
        assert 'speed' in model_info
        assert 'quality' in model_info


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

