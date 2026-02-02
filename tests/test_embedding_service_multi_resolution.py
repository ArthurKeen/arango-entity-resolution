"""
Comprehensive tests for EmbeddingService multi-resolution support

Tests legacy mode, multi-resolution mode, and metadata consistency.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any
from datetime import datetime

# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from entity_resolution.services.embedding_service import (
    EmbeddingService,
    SENTENCE_TRANSFORMERS_AVAILABLE,
    DEFAULT_EMBEDDING_FIELD,
    DEFAULT_EMBEDDING_FIELD_COARSE,
    DEFAULT_EMBEDDING_FIELD_FINE,
    DEFAULT_METADATA_VERSION,
    LEGACY_METADATA_VERSION
)


class TestLegacyMode:
    """Test legacy mode (backward compatibility)"""
    
    def test_legacy_init_default(self):
        """Test legacy mode initialization with defaults"""
        service = EmbeddingService()
        
        assert service.multi_resolution_mode is False
        assert service.model_name == 'all-MiniLM-L6-v2'
        assert service.embedding_field == DEFAULT_EMBEDDING_FIELD
        assert service.coarse_model_name is None
        assert service.fine_model_name is None
    
    def test_legacy_init_custom_field(self):
        """Test legacy mode with custom embedding field"""
        service = EmbeddingService(embedding_field='custom_embedding')
        
        assert service.multi_resolution_mode is False
        assert service.embedding_field == 'custom_embedding'
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_legacy_generate_embedding(self, mock_st_class):
        """Test legacy mode embedding generation"""
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
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_legacy_store_embeddings(self, mock_st_class):
        """Test legacy mode embedding storage"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model
        
        mock_collection = Mock()
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        service._embedding_dim = 384
        
        records = [{'_key': 'doc1'}, {'_key': 'doc2'}]
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        result = service.store_embeddings('test_collection', records, embeddings)
        
        assert result['updated'] == 2
        assert result['failed'] == 0
        
        # Check metadata structure
        update_calls = mock_collection.update.call_args_list
        for call in update_calls:
            update_data = call[0][0]
            assert DEFAULT_EMBEDDING_FIELD in update_data
            assert 'embedding_metadata' in update_data
            metadata = update_data['embedding_metadata']
            assert metadata['version'] == LEGACY_METADATA_VERSION
            assert 'model' in metadata
            assert 'dim' in metadata
            assert 'timestamp' in metadata
            assert 'profile' in metadata
    
    def test_legacy_mode_rejects_multi_resolution_methods(self):
        """Test that legacy mode rejects multi-resolution methods"""
        service = EmbeddingService()
        
        with pytest.raises(ValueError, match="multi_resolution_mode"):
            _ = service.coarse_model
        
        with pytest.raises(ValueError, match="multi_resolution_mode"):
            _ = service.fine_model
        
        with pytest.raises(ValueError, match="multi_resolution_mode"):
            _ = service.coarse_embedding_dim
        
        with pytest.raises(ValueError, match="multi_resolution_mode"):
            _ = service.fine_embedding_dim
        
        with pytest.raises(ValueError, match="multi_resolution_mode"):
            service.generate_coarse_embedding({'name': 'Test'})
        
        with pytest.raises(ValueError, match="multi_resolution_mode"):
            service.generate_fine_embedding({'name': 'Test'})


class TestMultiResolutionMode:
    """Test multi-resolution mode"""
    
    def test_multi_resolution_init(self):
        """Test multi-resolution mode initialization"""
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2',
            fine_model_name='all-mpnet-base-v2'
        )
        
        assert service.multi_resolution_mode is True
        assert service.coarse_model_name == 'all-MiniLM-L6-v2'
        assert service.fine_model_name == 'all-mpnet-base-v2'
        assert service.embedding_field_coarse == DEFAULT_EMBEDDING_FIELD_COARSE
        assert service.embedding_field_fine == DEFAULT_EMBEDDING_FIELD_FINE
    
    def test_multi_resolution_init_missing_coarse_model(self):
        """Test that missing coarse_model_name raises error"""
        with pytest.raises(ValueError, match="coarse_model_name"):
            EmbeddingService(
                multi_resolution_mode=True,
                fine_model_name='all-mpnet-base-v2'
            )
    
    def test_multi_resolution_init_fine_defaults_to_model_name(self):
        """Test that fine_model_name defaults to model_name"""
        service = EmbeddingService(
            model_name='all-mpnet-base-v2',
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2'
        )
        
        assert service.fine_model_name == 'all-mpnet-base-v2'
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_multi_resolution_generate_coarse_embedding(self, mock_st_class):
        """Test coarse embedding generation"""
        mock_coarse_model = Mock()
        mock_coarse_model.get_sentence_embedding_dimension.return_value = 384
        mock_coarse_embedding = np.array([0.1, 0.2, 0.3])
        mock_coarse_model.encode.return_value = mock_coarse_embedding
        
        mock_fine_model = Mock()
        mock_fine_model.get_sentence_embedding_dimension.return_value = 768
        
        mock_st_class.side_effect = [mock_coarse_model, mock_fine_model]
        
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2',
            fine_model_name='all-mpnet-base-v2'
        )
        
        record = {'name': 'John Smith', 'company': 'Acme'}
        coarse_embedding = service.generate_coarse_embedding(record)
        
        assert isinstance(coarse_embedding, np.ndarray)
        assert coarse_embedding.shape == (3,)
        np.testing.assert_array_equal(coarse_embedding, mock_coarse_embedding)
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_multi_resolution_generate_fine_embedding(self, mock_st_class):
        """Test fine embedding generation"""
        mock_fine_model = Mock()
        mock_fine_model.get_sentence_embedding_dimension.return_value = 768
        mock_fine_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        mock_fine_model.encode.return_value = mock_fine_embedding
        mock_st_class.return_value = mock_fine_model
        
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2',
            fine_model_name='all-mpnet-base-v2'
        )
        
        record = {'name': 'John Smith', 'company': 'Acme'}
        fine_embedding = service.generate_fine_embedding(record)
        
        assert isinstance(fine_embedding, np.ndarray)
        assert fine_embedding.shape == (6,)
        np.testing.assert_array_equal(fine_embedding, mock_fine_embedding)
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_multi_resolution_store_embeddings(self, mock_st_class):
        """Test multi-resolution mode embedding storage"""
        mock_coarse_model = Mock()
        mock_coarse_model.get_sentence_embedding_dimension.return_value = 384
        
        mock_fine_model = Mock()
        mock_fine_model.get_sentence_embedding_dimension.return_value = 768
        
        mock_st_class.side_effect = [mock_coarse_model, mock_fine_model]
        
        mock_collection = Mock()
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2',
            fine_model_name='all-mpnet-base-v2',
            db_manager=mock_db_manager
        )
        service._coarse_embedding_dim = 384
        service._fine_embedding_dim = 768
        
        records = [{'_key': 'doc1'}, {'_key': 'doc2'}]
        coarse_embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        fine_embeddings = np.array([[0.5, 0.6, 0.7], [0.8, 0.9, 1.0]])
        
        result = service.store_embeddings(
            'test_collection',
            records,
            None,
            coarse_embeddings=coarse_embeddings,
            fine_embeddings=fine_embeddings
        )
        
        assert result['updated'] == 2
        assert result['failed'] == 0
        
        # Check metadata structure
        update_calls = mock_collection.update.call_args_list
        for call in update_calls:
            update_data = call[0][0]
            assert DEFAULT_EMBEDDING_FIELD_COARSE in update_data
            assert DEFAULT_EMBEDDING_FIELD_FINE in update_data
            assert DEFAULT_EMBEDDING_FIELD not in update_data  # Legacy field not used
            assert 'embedding_metadata' in update_data
            metadata = update_data['embedding_metadata']
            assert metadata['version'] == DEFAULT_METADATA_VERSION
            assert 'model_coarse' in metadata
            assert 'model_fine' in metadata
            assert 'dim_coarse' in metadata
            assert 'dim_fine' in metadata
            assert 'timestamp' in metadata
            assert 'profile' in metadata
    
    def test_multi_resolution_store_embeddings_missing_coarse(self):
        """Test that missing coarse embeddings raises error"""
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2'
        )
        
        records = [{'_key': 'doc1'}]
        fine_embeddings = np.array([[0.1, 0.2]])
        
        with pytest.raises(ValueError, match="coarse_embeddings"):
            service.store_embeddings(
                'test',
                records,
                None,
                fine_embeddings=fine_embeddings
            )
    
    def test_multi_resolution_mode_rejects_legacy_methods(self):
        """Test that multi-resolution mode rejects legacy methods"""
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2',
            fine_model_name='all-mpnet-base-v2'
        )
        
        with pytest.raises(ValueError, match="legacy mode"):
            service.generate_embedding({'name': 'Test'})
        
        with pytest.raises(ValueError, match="legacy mode"):
            service.generate_embeddings_batch([{'name': 'Test'}])
        
        with pytest.raises(ValueError, match="multi_resolution_mode"):
            _ = service.embedding_dim


class TestMetadataConsistency:
    """Test metadata consistency across modes"""
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_legacy_metadata_structure(self, mock_st_class):
        """Test legacy mode metadata structure"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model
        
        mock_collection = Mock()
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(
            model_name='all-MiniLM-L6-v2',
            profile='test_profile',
            db_manager=mock_db_manager
        )
        service._embedding_dim = 384
        
        records = [{'_key': 'doc1'}]
        embeddings = np.array([[0.1, 0.2, 0.3]])
        
        service.store_embeddings('test', records, embeddings)
        
        update_data = mock_collection.update.call_args[0][0]
        metadata = update_data['embedding_metadata']
        
        # Check required fields
        assert metadata['version'] == LEGACY_METADATA_VERSION
        assert metadata['model'] == 'all-MiniLM-L6-v2'
        assert metadata['dim'] == 384
        assert metadata['profile'] == 'test_profile'
        assert 'timestamp' in metadata
        
        # Check timestamp is valid ISO format
        datetime.fromisoformat(metadata['timestamp'])
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_multi_resolution_metadata_structure(self, mock_st_class):
        """Test multi-resolution mode metadata structure"""
        mock_coarse_model = Mock()
        mock_coarse_model.get_sentence_embedding_dimension.return_value = 384
        
        mock_fine_model = Mock()
        mock_fine_model.get_sentence_embedding_dimension.return_value = 768
        
        mock_st_class.side_effect = [mock_coarse_model, mock_fine_model]
        
        mock_collection = Mock()
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2',
            fine_model_name='all-mpnet-base-v2',
            profile='test_profile',
            db_manager=mock_db_manager
        )
        service._coarse_embedding_dim = 384
        service._fine_embedding_dim = 768
        
        records = [{'_key': 'doc1'}]
        coarse_embeddings = np.array([[0.1, 0.2]])
        fine_embeddings = np.array([[0.3, 0.4, 0.5]])
        
        service.store_embeddings(
            'test',
            records,
            None,
            coarse_embeddings=coarse_embeddings,
            fine_embeddings=fine_embeddings
        )
        
        update_data = mock_collection.update.call_args[0][0]
        metadata = update_data['embedding_metadata']
        
        # Check required fields
        assert metadata['version'] == DEFAULT_METADATA_VERSION
        assert metadata['model_coarse'] == 'all-MiniLM-L6-v2'
        assert metadata['model_fine'] == 'all-mpnet-base-v2'
        assert metadata['dim_coarse'] == 384
        assert metadata['dim_fine'] == 768
        assert metadata['profile'] == 'test_profile'
        assert 'timestamp' in metadata
        
        # Check timestamp is valid ISO format
        datetime.fromisoformat(metadata['timestamp'])
        
        # Check legacy fields are not present
        assert 'model' not in metadata
        assert 'dim' not in metadata
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_metadata_timestamp_consistency(self, mock_st_class):
        """Test that metadata timestamps are consistent within a batch"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model
        
        mock_collection = Mock()
        mock_collection.update.return_value = None
        
        mock_db = Mock()
        mock_db.collection.return_value = mock_collection
        
        mock_db_manager = Mock()
        mock_db_manager.get_database.return_value = mock_db
        
        service = EmbeddingService(db_manager=mock_db_manager)
        service._embedding_dim = 384
        
        records = [{'_key': 'doc1'}, {'_key': 'doc2'}, {'_key': 'doc3'}]
        embeddings = np.array([[0.1], [0.2], [0.3]])
        
        service.store_embeddings('test', records, embeddings)
        
        # Check all updates have the same timestamp
        timestamps = []
        for call in mock_collection.update.call_args_list:
            update_data = call[0][0]
            timestamps.append(update_data['embedding_metadata']['timestamp'])
        
        assert len(set(timestamps)) == 1  # All timestamps should be identical


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""
    
    def test_default_behavior_unchanged(self):
        """Test that default behavior matches legacy mode"""
        service = EmbeddingService()
        
        assert service.multi_resolution_mode is False
        assert service.embedding_field == DEFAULT_EMBEDDING_FIELD
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_existing_code_still_works(self, mock_st_class):
        """Test that existing code using legacy API still works"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_st_class.return_value = mock_model
        
        # Simulate existing code
        service = EmbeddingService(model_name='all-MiniLM-L6-v2')
        record = {'name': 'John Smith'}
        embedding = service.generate_embedding(record)
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 3


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_multi_resolution_store_without_embeddings(self):
        """Test that multi-resolution mode requires embeddings"""
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2'
        )
        
        records = [{'_key': 'doc1'}]
        
        with pytest.raises(ValueError, match="coarse_embeddings"):
            service.store_embeddings('test', records, None)
    
    def test_multi_resolution_length_mismatch(self):
        """Test that length mismatches are caught"""
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2'
        )
        
        records = [{'_key': 'doc1'}]
        coarse_embeddings = np.array([[0.1], [0.2]])  # 2 embeddings, 1 record
        fine_embeddings = np.array([[0.3]])
        
        with pytest.raises(ValueError, match="must match"):
            service.store_embeddings(
                'test',
                records,
                None,
                coarse_embeddings=coarse_embeddings,
                fine_embeddings=fine_embeddings
            )
    
    @patch('entity_resolution.services.embedding_service.SentenceTransformer')
    def test_record_to_text_excludes_multi_resolution_fields(self, mock_st_class):
        """Test that _record_to_text excludes multi-resolution fields"""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model
        
        service = EmbeddingService(
            multi_resolution_mode=True,
            coarse_model_name='all-MiniLM-L6-v2',
            fine_model_name='all-mpnet-base-v2'
        )
        
        record = {
            'name': 'John Smith',
            'company': 'Acme',
            'embedding_vector_coarse': [0.1, 0.2],
            'embedding_vector_fine': [0.3, 0.4],
            'embedding_metadata': {'test': 'data'}
        }
        
        text = service._record_to_text(record)
        
        assert 'John Smith' in text
        assert 'Acme' in text
        assert 'embedding_vector_coarse' not in text
        assert 'embedding_vector_fine' not in text
        assert 'embedding_metadata' not in text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
