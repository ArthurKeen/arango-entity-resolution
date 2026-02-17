"""
LSH (Locality Sensitive Hashing) Blocking Strategy for Entity Resolution

Uses LSH with random hyperplanes to generate candidate pairs based on vector
embeddings. This is a coarse candidate generation method that can efficiently
find similar vectors without computing all pairwise similarities.

LSH Algorithm:
- Generates random hyperplanes (normalized vectors) for each hash table
- For each document vector, computes which side of each hyperplane it's on
- Combines hyperplane signs into a hash code
- Documents with similar hash codes are likely similar (high cosine similarity)
- Multiple hash tables (L) increase recall
- More hyperplanes per table (k) increase precision but decrease recall

Based on research:
- Charikar (2002): "Similarity Estimation Techniques from Rounding Algorithms"
- Uses random hyperplane LSH for cosine similarity

Implementation Strategy:
- Assumes embeddings are already stored in documents (use EmbeddingService first)
- Configurable number of hash tables (L) and hyperplanes per table (k)
- Deterministic hashing via random seed for reproducible tests
- Compatible output format with other blocking strategies
"""

import logging
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from arango.database import StandardDatabase
import numpy as np

from .base_strategy import BlockingStrategy
from ..utils.validation import validate_collection_name, validate_field_name
from ..utils.aql_builders import build_aql_filter_conditions


# Constants for LSH blocking configuration
DEFAULT_EMBEDDING_FIELD = 'embedding_vector'
DEFAULT_NUM_HASH_TABLES = 10  # L parameter
DEFAULT_NUM_HYPERPLANES = 8   # k parameter
DEFAULT_RANDOM_SEED = 42      # For deterministic hashing in tests
MINIMUM_VECTOR_MAGNITUDE = 1e-10  # Prevent division by zero


class LSHBlockingStrategy(BlockingStrategy):
    """
    LSH-based blocking using random hyperplanes for cosine similarity
    
    Generates candidate pairs by hashing document vectors into buckets using
    random hyperplanes. Documents in the same bucket are likely similar.
    
    Prerequisites:
    - Documents must have pre-computed embeddings (use EmbeddingService)
    - Embeddings should be stored in the specified embedding_field
    
    Attributes:
        embedding_field: Field name containing vector embeddings
        num_hash_tables: Number of hash tables (L) - more tables = higher recall
        num_hyperplanes: Number of hyperplanes per table (k) - more hyperplanes = higher precision, lower recall
        random_seed: Random seed for deterministic hashing (default: 42)
        blocking_field: Optional field for additional blocking (e.g., state, category)
    
    Example:
        >>> from entity_resolution.services.embedding_service import EmbeddingService
        >>> from entity_resolution.strategies.lsh_blocking import LSHBlockingStrategy
        >>> 
        >>> # First, ensure embeddings exist
        >>> embedding_service = EmbeddingService()
        >>> embedding_service.ensure_embeddings_exist(
        ...     'customers',
        ...     text_fields=['name', 'company', 'address']
        ... )
        >>> 
        >>> # Then use LSH blocking
        >>> strategy = LSHBlockingStrategy(
        ...     db=db,
        ...     collection='customers',
        ...     num_hash_tables=10,
        ...     num_hyperplanes=8,
        ...     random_seed=42  # For deterministic tests
        ... )
        >>> pairs = strategy.generate_candidates()
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        embedding_field: str = DEFAULT_EMBEDDING_FIELD,
        num_hash_tables: int = DEFAULT_NUM_HASH_TABLES,
        num_hyperplanes: int = DEFAULT_NUM_HYPERPLANES,
        random_seed: Optional[int] = DEFAULT_RANDOM_SEED,
        blocking_field: Optional[str] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        """
        Initialize LSH blocking strategy
        
        Args:
            db: ArangoDB database connection
            collection: Source collection name
            embedding_field: Field name containing embeddings (default: 'embedding_vector')
            num_hash_tables: Number of hash tables (L parameter, default: 10)
                - More tables increase recall but also increase computation
                - Typical range: 5-20
            num_hyperplanes: Number of hyperplanes per table (k parameter, default: 8)
                - More hyperplanes increase precision but decrease recall
                - Typical range: 4-16
            random_seed: Random seed for deterministic hyperplane generation (default: 42)
                - Set to None for non-deterministic (production) mode
                - Use fixed seed for reproducible tests
            blocking_field: Optional field to block on (e.g., 'state', 'category')
                If provided, only compares documents with matching blocking_field values
            filters: Optional filters to apply before blocking
            
        Raises:
            ValueError: If num_hash_tables < 1 or num_hyperplanes < 1
        """
        super().__init__(db, collection, filters)
        
        if num_hash_tables < 1:
            raise ValueError(
                f"num_hash_tables must be >= 1, got {num_hash_tables}"
            )
        
        if num_hyperplanes < 1:
            raise ValueError(
                f"num_hyperplanes must be >= 1, got {num_hyperplanes}"
            )
        
        self.embedding_field = validate_field_name(embedding_field)
        self.num_hash_tables = num_hash_tables
        self.num_hyperplanes = num_hyperplanes
        self.random_seed = random_seed
        self.blocking_field = validate_field_name(blocking_field) if blocking_field else None
        
        self.logger = logging.getLogger(__name__)
        
        # Generate hyperplanes (deterministic if seed is set)
        self._hyperplanes = self._generate_hyperplanes()
        
        # Additional stats specific to LSH blocking
        self._stats['embedding_field'] = self.embedding_field
        self._stats['num_hash_tables'] = self.num_hash_tables
        self._stats['num_hyperplanes'] = self.num_hyperplanes
        self._stats['random_seed'] = self.random_seed
        self._stats['blocking_field'] = self.blocking_field
    
    def _generate_hyperplanes(self) -> List[np.ndarray]:
        """
        Generate random hyperplanes for LSH hashing
        
        Creates num_hash_tables * num_hyperplanes hyperplanes total.
        Each hyperplane is a normalized random vector.
        
        Returns:
            List of hyperplane vectors, shape (num_hash_tables * num_hyperplanes, embedding_dim)
        """
        # Use deterministic RNG if seed is provided
        rng = np.random.RandomState(self.random_seed) if self.random_seed is not None else np.random
        
        # We need to know the embedding dimension first
        # For now, generate a placeholder - will be updated when we see actual embeddings
        # Use a reasonable default dimension (e.g., 384 for all-MiniLM-L6-v2)
        default_dim = 384
        
        # Generate random hyperplanes
        # Each hyperplane is a random vector sampled from standard normal distribution
        total_hyperplanes = self.num_hash_tables * self.num_hyperplanes
        hyperplanes = rng.randn(total_hyperplanes, default_dim)
        
        # Normalize each hyperplane to unit length
        norms = np.linalg.norm(hyperplanes, axis=1, keepdims=True)
        norms = np.where(norms < MINIMUM_VECTOR_MAGNITUDE, 1.0, norms)  # Avoid division by zero
        hyperplanes = hyperplanes / norms
        
        return hyperplanes
    
    def _compute_hash(self, vector: np.ndarray, table_idx: int) -> str:
        """
        Compute LSH hash for a vector using a specific hash table
        
        Args:
            vector: Embedding vector (normalized)
            table_idx: Index of the hash table (0 to num_hash_tables - 1)
            
        Returns:
            Hash string representing the bucket
        """
        # Get hyperplanes for this table
        start_idx = table_idx * self.num_hyperplanes
        end_idx = start_idx + self.num_hyperplanes
        table_hyperplanes = self._hyperplanes[start_idx:end_idx]
        
        # Compute which side of each hyperplane the vector is on
        # Sign of dot product: positive = one side, negative = other side
        signs = np.dot(table_hyperplanes, vector) >= 0
        
        # Convert boolean array to binary string, then to hex for hash
        binary_str = ''.join('1' if s else '0' for s in signs)
        
        # Use MD5 to create a compact hash (deterministic)
        hash_obj = hashlib.md5(binary_str.encode())
        return hash_obj.hexdigest()
    
    def _check_embeddings_exist(self) -> Dict[str, Any]:
        """
        Check if embeddings exist in the collection and get embedding dimension
        
        Returns:
            Dictionary with statistics about embedding coverage and dimension
        """
        # First check if we have any documents with embeddings
        query = f"""
            LET total = COUNT(FOR doc IN {self.collection} RETURN 1)
            LET with_embeddings = COUNT(
                FOR doc IN {self.collection}
                FILTER doc.{self.embedding_field} != null
                RETURN 1
            )
            LET sample_embedding = (
                FOR doc IN {self.collection}
                FILTER doc.{self.embedding_field} != null
                LIMIT 1
                RETURN doc.{self.embedding_field}
            )
            RETURN {{
                total: total,
                with_embeddings: with_embeddings,
                without_embeddings: total - with_embeddings,
                coverage_percent: with_embeddings > 0 ? (with_embeddings / total * 100) : 0.0,
                embedding_dim: LENGTH(sample_embedding) > 0 ? LENGTH(sample_embedding[0]) : null
            }}
        """
        
        cursor = self.db.aql.execute(query)
        stats = next(cursor)
        
        return stats
    
    def generate_candidates(self) -> List[Dict[str, Any]]:
        """
        Generate candidate pairs using LSH hashing
        
        Algorithm:
        1. Load all documents with embeddings
        2. For each document, compute LSH hash for each hash table
        3. Group documents by hash (bucket) within each table
        4. Generate candidate pairs from documents in the same bucket
        5. Deduplicate pairs across hash tables
        6. Normalize pairs to avoid duplicates (doc1_key < doc2_key)
        
        Returns:
            List of candidate pairs:
            [{
                'doc1_key': str,
                'doc2_key': str,
                'lsh_hash': str,  # Hash that matched
                'hash_table': int,  # Which hash table found this pair
                'method': 'lsh'
            }]
            
        Raises:
            RuntimeError: If no embeddings found in collection
        """
        start_time = time.time()
        
        # Check embedding coverage and get dimension
        embedding_stats = self._check_embeddings_exist()
        
        if embedding_stats['with_embeddings'] == 0:
            raise RuntimeError(
                f"No embeddings found in collection '{self.collection}'. "
                f"Use EmbeddingService.ensure_embeddings_exist() first."
            )
        
        embedding_dim = embedding_stats.get('embedding_dim')
        if embedding_dim is None:
            raise RuntimeError(
                f"Could not determine embedding dimension from collection '{self.collection}'"
            )
        
        # Regenerate hyperplanes with correct dimension if needed
        if self._hyperplanes.shape[1] != embedding_dim:
            self.logger.info(
                f"Regenerating hyperplanes for dimension {embedding_dim} "
                f"(was {self._hyperplanes.shape[1]})"
            )
            rng = np.random.RandomState(self.random_seed) if self.random_seed is not None else np.random
            total_hyperplanes = self.num_hash_tables * self.num_hyperplanes
            hyperplanes = rng.randn(total_hyperplanes, embedding_dim)
            norms = np.linalg.norm(hyperplanes, axis=1, keepdims=True)
            norms = np.where(norms < MINIMUM_VECTOR_MAGNITUDE, 1.0, norms)
            self._hyperplanes = hyperplanes / norms
        
        if embedding_stats['coverage_percent'] < 100:
            self.logger.warning(
                f"Only {embedding_stats['coverage_percent']:.1f}% of documents "
                f"have embeddings ({embedding_stats['with_embeddings']}/{embedding_stats['total']})"
            )
        
        self.logger.info(
            f"Generating LSH-based candidates with L={self.num_hash_tables}, "
            f"k={self.num_hyperplanes}, dim={embedding_dim}"
        )
        
        # Build filter conditions
        filter_conditions, filter_bind_vars = build_aql_filter_conditions(
            self.filters,
            var_name="doc",
            bind_var_prefix="filter",
        )
        filter_clause = " AND ".join(filter_conditions) if filter_conditions else "true"
        
        # Build blocking clause
        blocking_clause = ""
        if self.blocking_field:
            blocking_clause = f"AND doc1.{self.blocking_field} == doc2.{self.blocking_field}"
        
        # Load all documents with embeddings into memory
        # For large collections, this could be optimized with batching
        blocking_value_expr = f"doc.{self.blocking_field}" if self.blocking_field else "null"
        query = f"""
            FOR doc IN {self.collection}
            FILTER doc.{self.embedding_field} != null
            FILTER {filter_clause}
            RETURN {{
                _key: doc._key,
                embedding: doc.{self.embedding_field},
                blocking_value: {blocking_value_expr}  // null if blocking_field not set
            }}
        """
        
        cursor = self.db.aql.execute(query, bind_vars=filter_bind_vars)
        documents = list(cursor)
        
        if len(documents) == 0:
            self.logger.warning("No documents with embeddings found after filtering")
            return []
        
        self.logger.info(f"Processing {len(documents)} documents with embeddings")
        
        # Convert embeddings to numpy arrays
        doc_vectors = {}
        doc_blocking_values = {}
        for doc in documents:
            key = doc['_key']
            embedding = np.array(doc['embedding'], dtype=np.float32)
            # Normalize vector for cosine similarity
            norm = np.linalg.norm(embedding)
            if norm > MINIMUM_VECTOR_MAGNITUDE:
                embedding = embedding / norm
            doc_vectors[key] = embedding
            doc_blocking_values[key] = doc.get('blocking_value')
        
        # Build hash tables: table_idx -> hash -> list of document keys
        hash_tables: Dict[int, Dict[str, List[str]]] = {}
        for table_idx in range(self.num_hash_tables):
            hash_tables[table_idx] = {}
        
        # Compute hashes for all documents
        for doc_key, vector in doc_vectors.items():
            for table_idx in range(self.num_hash_tables):
                hash_code = self._compute_hash(vector, table_idx)
                if hash_code not in hash_tables[table_idx]:
                    hash_tables[table_idx][hash_code] = []
                hash_tables[table_idx][hash_code].append(doc_key)
        
        # Generate candidate pairs from hash tables
        candidate_pairs = []
        seen_pairs = set()
        
        for table_idx, hash_table in hash_tables.items():
            for hash_code, doc_keys in hash_table.items():
                # Only consider buckets with multiple documents
                if len(doc_keys) < 2:
                    continue
                
                # Generate pairs within this bucket
                for i, key1 in enumerate(doc_keys):
                    for j, key2 in enumerate(doc_keys):
                        if i >= j:  # Avoid self-pairs and duplicates
                            continue
                        
                        # Apply blocking field constraint if specified
                        if self.blocking_field:
                            if doc_blocking_values[key1] != doc_blocking_values[key2]:
                                continue
                        
                        # Normalize pair (ensure key1 < key2)
                        if key1 > key2:
                            key1, key2 = key2, key1
                        
                        pair_tuple = (key1, key2)
                        if pair_tuple not in seen_pairs:
                            seen_pairs.add(pair_tuple)
                            candidate_pairs.append({
                                'doc1_key': key1,
                                'doc2_key': key2,
                                'lsh_hash': hash_code,
                                'hash_table': table_idx,
                                'method': 'lsh'
                            })
        
        # Normalize pairs (remove any remaining duplicates)
        candidate_pairs = self._normalize_pairs(candidate_pairs)
        
        execution_time = time.time() - start_time
        
        # Update statistics
        self._update_statistics(candidate_pairs, execution_time)
        self._stats['embedding_coverage_percent'] = embedding_stats['coverage_percent']
        self._stats['documents_with_embeddings'] = embedding_stats['with_embeddings']
        self._stats['embedding_dimension'] = embedding_dim
        self._stats['total_buckets'] = sum(len(ht) for ht in hash_tables.values())
        self._stats['non_empty_buckets'] = sum(
            len([b for b in buckets.values() if len(b) >= 2])
            for buckets in hash_tables.values()
        )
        
        self.logger.info(
            f"Generated {len(candidate_pairs)} candidate pairs in {execution_time:.2f}s "
            f"using {self.num_hash_tables} hash tables"
        )
        
        return candidate_pairs
    
    def __repr__(self) -> str:
        """String representation of the strategy"""
        return (
            f"LSHBlockingStrategy(collection='{self.collection}', "
            f"L={self.num_hash_tables}, k={self.num_hyperplanes}, "
            f"seed={self.random_seed})"
        )
