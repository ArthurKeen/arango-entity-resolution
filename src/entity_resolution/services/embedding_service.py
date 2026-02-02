"""
Embedding Service for Entity Resolution

Generates vector embeddings for database records using pre-trained sentence-transformers.
Designed for Tier 3 semantic blocking in Phase 2 of the entity resolution pipeline.

Based on research:
- Ebraheem et al. (2018): "Distributed Representations of Tuples for Entity Resolution"
- Starting with pre-trained models before moving to custom Siamese networks

Implementation Strategy:
- Use sentence-transformers for pre-trained embeddings (MVP)
- Support batch processing for efficiency
- Store embeddings in ArangoDB documents
- Track embedding metadata (model, version, timestamp)
"""

import logging
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING
from datetime import datetime
import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None  # type: ignore

from ..utils.database import DatabaseManager
from .tuple_embedding_serializer import TupleEmbeddingSerializer


# Constants for embedding service configuration
DEFAULT_BATCH_SIZE = 32
DEFAULT_EMBEDDING_BATCH_SIZE = 100
DEFAULT_MODEL = 'all-MiniLM-L6-v2'
DEFAULT_EMBEDDING_FIELD = 'embedding_vector'
DEFAULT_EMBEDDING_FIELD_COARSE = 'embedding_vector_coarse'
DEFAULT_EMBEDDING_FIELD_FINE = 'embedding_vector_fine'
DEFAULT_METADATA_VERSION = 'v2.0'  # Version for multi-resolution support
LEGACY_METADATA_VERSION = 'v1.0'  # Legacy version


class EmbeddingService:
    """
    Generate and manage vector embeddings for entity resolution
    
    Uses pre-trained sentence-transformers models to create semantic embeddings
    of database records. Embeddings enable similarity-based blocking (Tier 3) that
    can capture fuzzy matches missed by exact or text-based blocking.
    
    Attributes:
        model_name: Name of the sentence-transformers model to use
        device: Device for inference ('cpu' or 'cuda')
        embedding_dim: Dimensionality of generated embeddings
        embedding_field: Field name to store embeddings in documents
    
    Example:
        >>> service = EmbeddingService(model_name='all-MiniLM-L6-v2')
        >>> embedding = service.generate_embedding(
        ...     {"name": "John Smith", "company": "Acme Corp"}
        ... )
        >>> print(embedding.shape)  # (384,)
    """
    
    # Recommended models with their dimensions and characteristics
    SUPPORTED_MODELS = {
        'all-MiniLM-L6-v2': {
            'dim': 384,
            'speed': 'fast',
            'quality': 'good',
            'description': 'Fast and efficient, good for most use cases'
        },
        'all-mpnet-base-v2': {
            'dim': 768,
            'speed': 'moderate',
            'quality': 'excellent',
            'description': 'Best quality, slower but more accurate'
        },
        'all-distilroberta-v1': {
            'dim': 768,
            'speed': 'moderate',
            'quality': 'very good',
            'description': 'Balance of speed and quality'
        }
    }
    
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = 'cpu',
        embedding_field: str = DEFAULT_EMBEDDING_FIELD,
        db_manager: Optional[DatabaseManager] = None,
        multi_resolution_mode: bool = False,
        coarse_model_name: Optional[str] = None,
        fine_model_name: Optional[str] = None,
        embedding_field_coarse: str = DEFAULT_EMBEDDING_FIELD_COARSE,
        embedding_field_fine: str = DEFAULT_EMBEDDING_FIELD_FINE,
        profile: str = 'default',
        serializer: Optional[TupleEmbeddingSerializer] = None
    ):
        """
        Initialize the embedding service
        
        Args:
            model_name: Name of sentence-transformers model (default: all-MiniLM-L6-v2)
                Used for legacy mode or as fine model in multi-resolution mode
            device: Device for inference ('cpu' or 'cuda')
            embedding_field: Field name for storing embeddings in legacy mode 
                (default: 'embedding_vector')
            db_manager: Optional DatabaseManager instance for database operations
            multi_resolution_mode: If True, enables multi-resolution embeddings (coarse + fine)
                If False, uses legacy single embedding_vector field (default: False)
            coarse_model_name: Model name for coarse embeddings (required if multi_resolution_mode=True)
                Should be a faster, lower-dimension model (e.g., 'all-MiniLM-L6-v2')
            fine_model_name: Model name for fine embeddings (required if multi_resolution_mode=True)
                Should be a higher-quality model (e.g., 'all-mpnet-base-v2')
                If None, uses model_name
            embedding_field_coarse: Field name for coarse embeddings (default: 'embedding_vector_coarse')
            embedding_field_fine: Field name for fine embeddings (default: 'embedding_vector_fine')
            profile: Profile name for metadata tracking (default: 'default')
            serializer: Optional TupleEmbeddingSerializer for deterministic serialization.
                If None, uses default text concatenation (backward compatible).
            
        Raises:
            ImportError: If sentence-transformers is not installed
            ValueError: If multi_resolution_mode=True but coarse_model_name is None
            ValueError: If model_name is not supported
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for EmbeddingService. "
                "Install with: pip install sentence-transformers"
            )
        
        # Validate multi-resolution configuration
        if multi_resolution_mode:
            if coarse_model_name is None:
                raise ValueError(
                    "coarse_model_name is required when multi_resolution_mode=True"
                )
            if coarse_model_name not in self.SUPPORTED_MODELS:
                logging.warning(
                    f"Coarse model '{coarse_model_name}' not in recommended list. "
                    f"Supported models: {list(self.SUPPORTED_MODELS.keys())}"
                )
            if fine_model_name and fine_model_name not in self.SUPPORTED_MODELS:
                logging.warning(
                    f"Fine model '{fine_model_name}' not in recommended list. "
                    f"Supported models: {list(self.SUPPORTED_MODELS.keys())}"
                )
        else:
            # Legacy mode validation
            if model_name not in self.SUPPORTED_MODELS:
                logging.warning(
                    f"Model '{model_name}' not in recommended list. "
                    f"Supported models: {list(self.SUPPORTED_MODELS.keys())}"
                )
        
        self.multi_resolution_mode = multi_resolution_mode
        self.device = device
        self.profile = profile
        self.db_manager = db_manager or DatabaseManager()
        self.serializer = serializer  # Optional tuple serializer
        
        # Legacy mode configuration
        if not multi_resolution_mode:
            self.model_name = model_name
            self.embedding_field = embedding_field
            self.coarse_model_name = None
            self.fine_model_name = None
            self.embedding_field_coarse = None
            self.embedding_field_fine = None
        else:
            # Multi-resolution mode configuration
            self.coarse_model_name = coarse_model_name
            self.fine_model_name = fine_model_name or model_name
            self.embedding_field_coarse = embedding_field_coarse
            self.embedding_field_fine = embedding_field_fine
            # Keep model_name for backward compatibility, but it's not used in multi-res mode
            self.model_name = self.fine_model_name
            self.embedding_field = embedding_field  # Not used in multi-res mode
        
        # Lazy load models on first use
        self._model = None
        self._coarse_model = None
        self._fine_model = None
        self._embedding_dim = None
        self._coarse_embedding_dim = None
        self._fine_embedding_dim = None
        
        self.logger = logging.getLogger(__name__)
        mode_str = "multi-resolution" if multi_resolution_mode else "legacy"
        self.logger.info(
            f"Initialized EmbeddingService in {mode_str} mode with model={model_name}, device={device}"
        )
        if multi_resolution_mode:
            self.logger.info(
                f"  Coarse model: {coarse_model_name}, Fine model: {fine_model_name or model_name}"
            )
        if serializer:
            self.logger.info("Using TupleEmbeddingSerializer for deterministic serialization")
    
    @property
    def model(self) -> 'SentenceTransformer':
        """Lazy load the sentence-transformers model (legacy mode)"""
        if self._model is None:
            self.logger.info(f"Loading sentence-transformers model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._embedding_dim = self._model.get_sentence_embedding_dimension()
            self.logger.info(f"Model loaded successfully (dim={self._embedding_dim})")
        return self._model
    
    @property
    def coarse_model(self) -> 'SentenceTransformer':
        """Lazy load the coarse model (multi-resolution mode)"""
        if not self.multi_resolution_mode:
            raise ValueError("coarse_model is only available in multi_resolution_mode")
        if self._coarse_model is None:
            self.logger.info(f"Loading coarse model: {self.coarse_model_name}")
            self._coarse_model = SentenceTransformer(self.coarse_model_name, device=self.device)
            self._coarse_embedding_dim = self._coarse_model.get_sentence_embedding_dimension()
            self.logger.info(f"Coarse model loaded successfully (dim={self._coarse_embedding_dim})")
        return self._coarse_model
    
    @property
    def fine_model(self) -> 'SentenceTransformer':
        """Lazy load the fine model (multi-resolution mode)"""
        if not self.multi_resolution_mode:
            raise ValueError("fine_model is only available in multi_resolution_mode")
        if self._fine_model is None:
            self.logger.info(f"Loading fine model: {self.fine_model_name}")
            self._fine_model = SentenceTransformer(self.fine_model_name, device=self.device)
            self._fine_embedding_dim = self._fine_model.get_sentence_embedding_dimension()
            self.logger.info(f"Fine model loaded successfully (dim={self._fine_embedding_dim})")
        return self._fine_model
    
    @property
    def embedding_dim(self) -> int:
        """Get the dimensionality of embeddings (legacy mode)"""
        if self.multi_resolution_mode:
            raise ValueError("embedding_dim not available in multi_resolution_mode. Use coarse_embedding_dim or fine_embedding_dim")
        if self._embedding_dim is None:
            # Trigger model loading
            _ = self.model
        return self._embedding_dim
    
    @property
    def coarse_embedding_dim(self) -> int:
        """Get the dimensionality of coarse embeddings (multi-resolution mode)"""
        if not self.multi_resolution_mode:
            raise ValueError("coarse_embedding_dim is only available in multi_resolution_mode")
        if self._coarse_embedding_dim is None:
            _ = self.coarse_model
        return self._coarse_embedding_dim
    
    @property
    def fine_embedding_dim(self) -> int:
        """Get the dimensionality of fine embeddings (multi-resolution mode)"""
        if not self.multi_resolution_mode:
            raise ValueError("fine_embedding_dim is only available in multi_resolution_mode")
        if self._fine_embedding_dim is None:
            _ = self.fine_model
        return self._fine_embedding_dim
    
    def _record_to_text(
        self,
        record: Dict[str, Any],
        text_fields: Optional[List[str]] = None
    ) -> str:
        """
        Convert a database record to text for embedding
        
        Uses TupleEmbeddingSerializer if provided, otherwise falls back to
        default concatenation (backward compatible).
        
        Args:
            record: Database record as dictionary
            text_fields: List of field names to include (if None, uses all text fields)
                Note: If serializer is used, field_order takes precedence over text_fields
            
        Returns:
            Concatenated text string
            
        Example:
            >>> record = {"name": "John Smith", "company": "Acme", "city": "NYC"}
            >>> text = service._record_to_text(record, ["name", "company"])
            >>> print(text)  # "John Smith, Acme" or "John Smith | Acme" (if serializer)
        """
        # Use serializer if available
        if self.serializer:
            return self.serializer.serialize(record)
        
        # Fallback to original implementation (backward compatible)
        if text_fields is None:
            # Use all string fields except metadata
            excluded_fields = ['embedding_metadata']
            if self.multi_resolution_mode:
                excluded_fields.extend([self.embedding_field_coarse, self.embedding_field_fine])
            else:
                excluded_fields.append(self.embedding_field)
            
            text_fields = [
                k for k, v in record.items()
                if isinstance(v, str) and not k.startswith('_')
                and k not in excluded_fields
            ]
        
        # Extract and concatenate field values
        parts = []
        for field in text_fields:
            value = record.get(field)
            if value and isinstance(value, str):
                parts.append(value.strip())
        
        return ', '.join(parts)
    
    def generate_embedding(
        self,
        record: Dict[str, Any],
        text_fields: Optional[List[str]] = None
    ) -> np.ndarray:
        """
        Generate embedding for a single record (legacy mode)
        
        Args:
            record: Database record as dictionary
            text_fields: Optional list of fields to use for embedding
            
        Returns:
            Numpy array of shape (embedding_dim,)
            
        Example:
            >>> embedding = service.generate_embedding(
            ...     {"name": "John Smith", "company": "Acme Corp"},
            ...     text_fields=["name", "company"]
            ... )
            >>> print(embedding.shape)  # (384,)
        """
        if self.multi_resolution_mode:
            raise ValueError(
                "generate_embedding() is for legacy mode only. "
                "Use generate_coarse_embedding() and generate_fine_embedding() "
                "in multi-resolution mode."
            )
        text = self._record_to_text(record, text_fields)
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding
    
    def generate_coarse_embedding(
        self,
        record: Dict[str, Any],
        text_fields: Optional[List[str]] = None
    ) -> np.ndarray:
        """
        Generate coarse embedding for a single record (multi-resolution mode)
        
        Args:
            record: Database record as dictionary
            text_fields: Optional list of fields to use for embedding
            
        Returns:
            Numpy array of shape (coarse_embedding_dim,)
            
        Raises:
            ValueError: If not in multi_resolution_mode
        """
        if not self.multi_resolution_mode:
            raise ValueError("generate_coarse_embedding() requires multi_resolution_mode=True")
        text = self._record_to_text(record, text_fields)
        embedding = self.coarse_model.encode(text, convert_to_numpy=True)
        return embedding
    
    def generate_fine_embedding(
        self,
        record: Dict[str, Any],
        text_fields: Optional[List[str]] = None
    ) -> np.ndarray:
        """
        Generate fine embedding for a single record (multi-resolution mode)
        
        Args:
            record: Database record as dictionary
            text_fields: Optional list of fields to use for embedding
            
        Returns:
            Numpy array of shape (fine_embedding_dim,)
            
        Raises:
            ValueError: If not in multi_resolution_mode
        """
        if not self.multi_resolution_mode:
            raise ValueError("generate_fine_embedding() requires multi_resolution_mode=True")
        text = self._record_to_text(record, text_fields)
        embedding = self.fine_model.encode(text, convert_to_numpy=True)
        return embedding
    
    def generate_embeddings_batch(
        self,
        records: List[Dict[str, Any]],
        text_fields: Optional[List[str]] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate embeddings for a batch of records (legacy mode)
        
        Batch processing is significantly faster than processing records one at a time.
        Recommended for generating embeddings for large collections.
        
        Args:
            records: List of database records
            text_fields: Optional list of fields to use for embedding
            batch_size: Batch size for processing (default: 32)
            show_progress: Whether to show progress bar
            
        Returns:
            Numpy array of shape (num_records, embedding_dim)
            
        Raises:
            ValueError: If records is None or contains invalid types
            ValueError: If in multi_resolution_mode
            
        Example:
            >>> records = [
            ...     {"name": "John Smith", "company": "Acme"},
            ...     {"name": "Jane Doe", "company": "TechCo"}
            ... ]
            >>> embeddings = service.generate_embeddings_batch(records)
            >>> print(embeddings.shape)  # (2, 384)
        """
        if self.multi_resolution_mode:
            raise ValueError(
                "generate_embeddings_batch() is for legacy mode only. "
                "Use generate_coarse_embeddings_batch() and generate_fine_embeddings_batch() "
                "in multi-resolution mode."
            )
        
        # Input validation
        if records is None:
            raise ValueError("records cannot be None")
        
        if not isinstance(records, list):
            raise ValueError(f"records must be a list, got {type(records)}")
        
        if not records:
            return np.array([])
        
        # Convert all records to text
        texts = [self._record_to_text(record, text_fields) for record in records]
        
        # Generate embeddings in batch
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def generate_coarse_embeddings_batch(
        self,
        records: List[Dict[str, Any]],
        text_fields: Optional[List[str]] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate coarse embeddings for a batch of records (multi-resolution mode)
        
        Args:
            records: List of database records
            text_fields: Optional list of fields to use for embedding
            batch_size: Batch size for processing (default: 32)
            show_progress: Whether to show progress bar
            
        Returns:
            Numpy array of shape (num_records, coarse_embedding_dim)
            
        Raises:
            ValueError: If not in multi_resolution_mode
        """
        if not self.multi_resolution_mode:
            raise ValueError("generate_coarse_embeddings_batch() requires multi_resolution_mode=True")
        
        if records is None:
            raise ValueError("records cannot be None")
        
        if not isinstance(records, list):
            raise ValueError(f"records must be a list, got {type(records)}")
        
        if not records:
            return np.array([])
        
        texts = [self._record_to_text(record, text_fields) for record in records]
        embeddings = self.coarse_model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def generate_fine_embeddings_batch(
        self,
        records: List[Dict[str, Any]],
        text_fields: Optional[List[str]] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate fine embeddings for a batch of records (multi-resolution mode)
        
        Args:
            records: List of database records
            text_fields: Optional list of fields to use for embedding
            batch_size: Batch size for processing (default: 32)
            show_progress: Whether to show progress bar
            
        Returns:
            Numpy array of shape (num_records, fine_embedding_dim)
            
        Raises:
            ValueError: If not in multi_resolution_mode
        """
        if not self.multi_resolution_mode:
            raise ValueError("generate_fine_embeddings_batch() requires multi_resolution_mode=True")
        
        if records is None:
            raise ValueError("records cannot be None")
        
        if not isinstance(records, list):
            raise ValueError(f"records must be a list, got {type(records)}")
        
        if not records:
            return np.array([])
        
        texts = [self._record_to_text(record, text_fields) for record in records]
        embeddings = self.fine_model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def store_embeddings(
        self,
        collection_name: str,
        records: List[Dict[str, Any]],
        embeddings: np.ndarray,
        database_name: Optional[str] = None,
        coarse_embeddings: Optional[np.ndarray] = None,
        fine_embeddings: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Store embeddings in ArangoDB collection
        
        Updates documents in the collection to include embedding vectors and metadata.
        Uses batch updates for efficiency.
        
        In legacy mode: stores single embedding_vector field
        In multi-resolution mode: stores embedding_vector_coarse and embedding_vector_fine fields
        
        Args:
            collection_name: Name of the collection
            records: List of records (must have '_key' field)
            embeddings: Numpy array of embeddings (num_records, embedding_dim) - legacy mode only
            database_name: Optional database name
            coarse_embeddings: Numpy array of coarse embeddings (multi-resolution mode only)
            fine_embeddings: Numpy array of fine embeddings (multi-resolution mode only)
            
        Returns:
            Statistics dictionary with counts of updated/failed documents
            
        Raises:
            ValueError: If records and embeddings have different lengths
            ValueError: If records are missing '_key' field
            ValueError: If multi-resolution mode but coarse/fine embeddings not provided
        """
        # Prepare metadata based on mode (validate before database access)
        if self.multi_resolution_mode:
            if coarse_embeddings is None or fine_embeddings is None:
                raise ValueError(
                    "coarse_embeddings and fine_embeddings are required in multi_resolution_mode"
                )
            if len(records) != len(coarse_embeddings) or len(records) != len(fine_embeddings):
                raise ValueError(
                    f"Number of records ({len(records)}) must match "
                    f"number of coarse ({len(coarse_embeddings)}) and fine ({len(fine_embeddings)}) embeddings"
                )
            
            metadata = {
                'model_coarse': self.coarse_model_name,
                'model_fine': self.fine_model_name,
                'dim_coarse': self.coarse_embedding_dim,
                'dim_fine': self.fine_embedding_dim,
                'timestamp': datetime.utcnow().isoformat(),
                'version': DEFAULT_METADATA_VERSION,
                'profile': self.profile
            }
            
            # Prepare batch update for multi-resolution mode
            updates = []
            for record, coarse_emb, fine_emb in zip(records, coarse_embeddings, fine_embeddings):
                if '_key' not in record:
                    raise ValueError(f"Record missing '_key' field: {record}")
                
                updates.append({
                    '_key': record['_key'],
                    self.embedding_field_coarse: coarse_emb.tolist(),
                    self.embedding_field_fine: fine_emb.tolist(),
                    'embedding_metadata': metadata
                })
        else:
            # Legacy mode
            if embeddings is None:
                raise ValueError("embeddings are required in legacy mode")
            if len(records) != len(embeddings):
                raise ValueError(
                    f"Number of records ({len(records)}) must match "
                    f"number of embeddings ({len(embeddings)})"
                )
            
            metadata = {
                'model': self.model_name,
                'dim': self.embedding_dim,
                'timestamp': datetime.utcnow().isoformat(),
                'version': LEGACY_METADATA_VERSION,
                'profile': self.profile
            }
            
            # Prepare batch update for legacy mode
            updates = []
            for record, embedding in zip(records, embeddings):
                if '_key' not in record:
                    raise ValueError(f"Record missing '_key' field: {record}")
                
                updates.append({
                    '_key': record['_key'],
                    self.embedding_field: embedding.tolist(),
                    'embedding_metadata': metadata
                })
        
        # Get database and collection
        db = self.db_manager.get_database(database_name)
        collection = db.collection(collection_name)
        
        # Execute batch update
        mode_str = "multi-resolution" if self.multi_resolution_mode else "legacy"
        self.logger.info(
            f"Storing {len(updates)} embeddings ({mode_str} mode) in collection '{collection_name}'"
        )
        
        updated = 0
        failed = 0
        
        try:
            # Use update_many for batch operation
            for update in updates:
                try:
                    collection.update(update)
                    updated += 1
                except Exception as e:
                    self.logger.error(f"Failed to update {update['_key']}: {e}")
                    failed += 1
        except Exception as e:
            self.logger.error(f"Batch update failed: {e}")
            raise
        
        result = {
            'updated': updated,
            'failed': failed,
            'total': len(updates)
        }
        
        self.logger.info(
            f"Embedding storage complete: {updated} updated, {failed} failed"
        )
        
        return result
    
    def ensure_embeddings_exist(
        self,
        collection_name: str,
        text_fields: List[str],
        database_name: Optional[str] = None,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Ensure all documents in a collection have embeddings
        
        Checks for missing embeddings and generates them in batch. Useful for
        initial setup or when adding embeddings to an existing collection.
        
        In legacy mode: checks for embedding_vector field
        In multi-resolution mode: checks for embedding_vector_coarse and embedding_vector_fine fields
        
        Args:
            collection_name: Name of the collection
            text_fields: List of fields to use for embedding generation
            database_name: Optional database name
            batch_size: Batch size for processing
            force_regenerate: If True, regenerate all embeddings
            
        Returns:
            Statistics dictionary with counts
            
        Example:
            >>> stats = service.ensure_embeddings_exist(
            ...     'customers',
            ...     text_fields=['name', 'company', 'address']
            ... )
            >>> print(f"Generated {stats['generated']} new embeddings")
        """
        db = self.db_manager.get_database(database_name)
        collection = db.collection(collection_name)
        
        # Find documents without embeddings based on mode
        if force_regenerate:
            query = f"FOR doc IN {collection_name} RETURN doc"
        elif self.multi_resolution_mode:
            query = f"""
                FOR doc IN {collection_name}
                FILTER doc.{self.embedding_field_coarse} == null 
                    OR doc.{self.embedding_field_fine} == null
                RETURN doc
            """
        else:
            query = f"""
                FOR doc IN {collection_name}
                FILTER doc.{self.embedding_field} == null
                RETURN doc
            """
        
        cursor = db.aql.execute(query)
        documents = list(cursor)
        
        if not documents:
            mode_str = "multi-resolution" if self.multi_resolution_mode else "legacy"
            self.logger.info(
                f"All documents in '{collection_name}' already have embeddings ({mode_str} mode)"
            )
            return {
                'total_docs': collection.count(),
                'generated': 0,
                'updated': 0,
                'failed': 0
            }
        
        self.logger.info(
            f"Found {len(documents)} documents {'to regenerate' if force_regenerate else 'without embeddings'}"
        )
        
        # Process in batches
        total_updated = 0
        total_failed = 0
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            if self.multi_resolution_mode:
                # Generate coarse and fine embeddings
                coarse_embeddings = self.generate_coarse_embeddings_batch(
                    batch, text_fields, batch_size=32
                )
                fine_embeddings = self.generate_fine_embeddings_batch(
                    batch, text_fields, batch_size=32
                )
                
                # Store embeddings
                result = self.store_embeddings(
                    collection_name, batch, None, database_name,
                    coarse_embeddings=coarse_embeddings,
                    fine_embeddings=fine_embeddings
                )
            else:
                # Generate embeddings (legacy mode)
                embeddings = self.generate_embeddings_batch(batch, text_fields, batch_size=32)
                
                # Store embeddings
                result = self.store_embeddings(
                    collection_name, batch, embeddings, database_name
                )
            
            total_updated += result['updated']
            total_failed += result['failed']
            
            self.logger.info(
                f"Processed batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}: "
                f"{result['updated']} updated"
            )
        
        return {
            'total_docs': collection.count(),
            'generated': len(documents),
            'updated': total_updated,
            'failed': total_failed
        }
    
    def get_embedding_stats(
        self,
        collection_name: str,
        database_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get statistics about embeddings in a collection
        
        Args:
            collection_name: Name of the collection
            database_name: Optional database name
            
        Returns:
            Dictionary with statistics (total, with_embeddings, without_embeddings, etc.)
        """
        db = self.db_manager.get_database(database_name)
        
        # Count total documents
        total_query = f"RETURN COUNT(FOR doc IN {collection_name} RETURN 1)"
        total = db.aql.execute(total_query).next()
        
        # Count documents with embeddings
        with_embeddings_query = f"""
            RETURN COUNT(
                FOR doc IN {collection_name}
                FILTER doc.{self.embedding_field} != null
                RETURN 1
            )
        """
        with_embeddings = db.aql.execute(with_embeddings_query).next()
        
        # Get embedding metadata from a sample document
        sample_query = f"""
            FOR doc IN {collection_name}
            FILTER doc.{self.embedding_field} != null
            LIMIT 1
            RETURN doc.embedding_metadata
        """
        cursor = db.aql.execute(sample_query)
        sample_metadata = next(cursor, None)
        
        return {
            'collection': collection_name,
            'total_documents': total,
            'with_embeddings': with_embeddings,
            'without_embeddings': total - with_embeddings,
            'coverage_percent': (with_embeddings / total * 100) if total > 0 else 0,
            'sample_metadata': sample_metadata
        }

