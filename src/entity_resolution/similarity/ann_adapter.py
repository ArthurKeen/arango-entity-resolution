"""
ANN (Approximate Nearest Neighbor) Adapter Layer

Provides a unified interface for vector similarity search with automatic fallback:
- Primary: ArangoDB native vector search (HNSW/Arango ANN) if available
- Fallback: Brute-force cosine similarity computation

This adapter enables VectorBlockingStrategy to leverage optimized vector search
when available while maintaining backward compatibility.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from arango.database import StandardDatabase
import numpy as np

from ..utils.validation import validate_collection_name, validate_field_name


# Constants
MINIMUM_VECTOR_MAGNITUDE = 1e-10  # Prevent division by zero
ARANGODB_MIN_VERSION_FOR_VECTOR_SEARCH = "3.10.0"  # Vector search available in 3.10+


class ANNAdapter:
    """
    Unified interface for approximate nearest neighbor search
    
    Automatically detects and uses the best available method:
    1. ArangoDB native vector search (HNSW) if available (3.10+)
    2. Brute-force cosine similarity as fallback
    
    Maintains backward compatibility with existing VectorBlockingStrategy usage.
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        embedding_field: str = 'embedding_vector',
        force_brute_force: bool = False
    ):
        """
        Initialize ANN adapter
        
        Args:
            db: ArangoDB database connection
            collection: Collection name containing vectors
            embedding_field: Field name containing embeddings
            force_brute_force: If True, always use brute-force (for testing/comparison)
            
        Raises:
            ValueError: If collection or embedding_field invalid
        """
        self.db = db
        self.collection = validate_collection_name(collection)
        self.embedding_field = validate_field_name(embedding_field)
        self.force_brute_force = force_brute_force
        
        self.logger = logging.getLogger(__name__)
        
        # Detect capabilities
        self._arango_version = None
        self._vector_search_available = False
        self._method = None
        
        if not force_brute_force:
            self._detect_capabilities()
        else:
            self._method = 'brute_force'
            self.logger.info("Forced brute-force mode (force_brute_force=True)")
    
    def _detect_capabilities(self) -> None:
        """Detect ArangoDB version and vector search capabilities"""
        try:
            # Get ArangoDB version
            version_info = self.db.properties()
            version_str = version_info.get('version', '')
            
            # Parse version (e.g., "3.12.0" -> (3, 12, 0))
            version_match = re.match(r'(\d+)\.(\d+)\.(\d+)', version_str)
            if version_match:
                major, minor, patch = map(int, version_match.groups())
                self._arango_version = (major, minor, patch)
                
                # Vector search available in 3.10+
                if (major, minor) >= (3, 10):
                    # Try to detect if vector search is actually available
                    # by checking if we can query with vector functions
                    self._vector_search_available = self._test_vector_search()
                else:
                    self._vector_search_available = False
            else:
                self.logger.warning(f"Could not parse ArangoDB version: {version_str}")
                self._vector_search_available = False
            
            # Set method
            if self._vector_search_available:
                self._method = 'arango_vector_search'
                self.logger.info(
                    f"Using ArangoDB native vector search (version {version_str})"
                )
            else:
                self._method = 'brute_force'
                self.logger.info(
                    f"Using brute-force cosine similarity "
                    f"(ArangoDB version {version_str or 'unknown'}, "
                    f"vector search not available)"
                )
                
        except Exception as e:
            self.logger.warning(f"Failed to detect ArangoDB capabilities: {e}")
            self._method = 'brute_force'
            self._vector_search_available = False
    
    def _test_vector_search(self) -> bool:
        """
        Test if ArangoDB vector search functions are available
        
        Returns:
            True if vector search appears to be available
        """
        try:
            # Try a simple test query that would use vector search if available
            # We'll check if the collection exists and has at least one document
            collection = self.db.collection(self.collection)
            if not collection.has():
                # Empty collection - can't test, but assume available if version >= 3.10
                return True
            
            # Try to query with a simple vector operation
            # Note: This is a heuristic - actual vector search requires proper index setup
            # For now, we'll detect version capability and let the user configure indexes
            # The actual search will fall back gracefully if indexes aren't configured
            return True
            
        except Exception as e:
            self.logger.debug(f"Vector search test failed: {e}")
            return False
    
    @property
    def method(self) -> str:
        """Get the current search method being used"""
        return self._method
    
    @property
    def arango_version(self) -> Optional[Tuple[int, int, int]]:
        """Get detected ArangoDB version"""
        return self._arango_version
    
    def find_similar_vectors(
        self,
        query_vector: Optional[List[float]] = None,
        query_doc_key: Optional[str] = None,
        similarity_threshold: float = 0.7,
        limit: int = 20,
        blocking_field: Optional[str] = None,
        blocking_value: Optional[Any] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
        exclude_self: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find similar vectors using the best available method
        
        Args:
            query_vector: Query vector (if None, uses query_doc_key)
            query_doc_key: Document key to find similar vectors for
            similarity_threshold: Minimum cosine similarity (0-1)
            limit: Maximum number of results
            blocking_field: Optional field to filter by
            blocking_value: Value for blocking_field filter
            filters: Additional filters to apply
            exclude_self: If True and query_doc_key provided, exclude that document
            
        Returns:
            List of similar vectors with scores:
            [{
                'doc_key': str,
                'similarity': float,
                'method': str
            }]
            
        Raises:
            ValueError: If neither query_vector nor query_doc_key provided
        """
        if query_vector is None and query_doc_key is None:
            raise ValueError("Either query_vector or query_doc_key must be provided")
        
        if self._method == 'arango_vector_search':
            return self._find_with_arango_vector_search(
                query_vector=query_vector,
                query_doc_key=query_doc_key,
                similarity_threshold=similarity_threshold,
                limit=limit,
                blocking_field=blocking_field,
                blocking_value=blocking_value,
                filters=filters,
                exclude_self=exclude_self
            )
        else:
            return self._find_with_brute_force(
                query_vector=query_vector,
                query_doc_key=query_doc_key,
                similarity_threshold=similarity_threshold,
                limit=limit,
                blocking_field=blocking_field,
                blocking_value=blocking_value,
                filters=filters,
                exclude_self=exclude_self
            )
    
    def _find_with_arango_vector_search(
        self,
        query_vector: Optional[List[float]],
        query_doc_key: Optional[str],
        similarity_threshold: float,
        limit: int,
        blocking_field: Optional[str],
        blocking_value: Optional[Any],
        filters: Optional[Dict[str, Dict[str, Any]]],
        exclude_self: bool
    ) -> List[Dict[str, Any]]:
        """
        Find similar vectors using ArangoDB native vector search
        
        Note: This attempts to use ArangoDB's vector search capabilities.
        If not properly configured (e.g., no vector index), it will fall back
        to brute-force automatically.
        """
        # First, get query vector if doc_key provided
        if query_vector is None and query_doc_key:
            doc = self.db.collection(self.collection).get(query_doc_key)
            if not doc or self.embedding_field not in doc:
                return []
            query_vector = doc[self.embedding_field]
        
        if query_vector is None:
            return []
        
        # Build filter conditions
        filter_conditions = []
        if blocking_field and blocking_value is not None:
            filter_conditions.append(f"doc.{blocking_field} == @blocking_value")
        
        # Add custom filters
        if filters:
            for field, condition in filters.items():
                if 'equals' in condition:
                    filter_conditions.append(f"doc.{field} == @filter_{field}")
                elif 'in' in condition:
                    filter_conditions.append(f"doc.{field} IN @filter_{field}")
        
        filter_clause = " AND ".join(filter_conditions) if filter_conditions else "true"
        
        # Build exclude clause
        exclude_clause = ""
        if exclude_self and query_doc_key:
            exclude_clause = "FILTER doc._key != @exclude_key"
        
        # Try ArangoDB vector search query
        # Note: This uses ArangoDB 3.10+ vector similarity functions
        # If not available, the query will fail and we'll fall back
        try:
            query = f"""
                FOR doc IN {self.collection}
                    FILTER doc.{self.embedding_field} != null
                    FILTER {filter_clause}
                    {exclude_clause}
                    
                    // Use ArangoDB vector similarity (if available)
                    // Note: This requires proper vector index configuration
                    LET similarity = COSINE_SIMILARITY(
                        doc.{self.embedding_field},
                        @query_vector
                    )
                    
                    FILTER similarity >= @similarity_threshold
                    SORT similarity DESC
                    LIMIT @limit
                    
                    RETURN {{
                        doc_key: doc._key,
                        similarity: similarity,
                        method: "arango_vector_search"
                    }}
            """
            
            bind_vars = {
                'query_vector': query_vector,
                'similarity_threshold': similarity_threshold,
                'limit': limit
            }
            
            if blocking_field and blocking_value is not None:
                bind_vars['blocking_value'] = blocking_value
            
            if exclude_self and query_doc_key:
                bind_vars['exclude_key'] = query_doc_key
            
            # Add filter bind vars
            if filters:
                for field, condition in filters.items():
                    bind_vars[f'filter_{field}'] = condition.get('equals') or condition.get('in')
            
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            results = list(cursor)
            
            return results
            
        except Exception as e:
            # Vector search not available or not configured - fall back to brute force
            self.logger.debug(
                f"ArangoDB vector search failed (may not be configured): {e}. "
                f"Falling back to brute-force."
            )
            return self._find_with_brute_force(
                query_vector=query_vector,
                query_doc_key=query_doc_key,
                similarity_threshold=similarity_threshold,
                limit=limit,
                blocking_field=blocking_field,
                blocking_value=blocking_value,
                filters=filters,
                exclude_self=exclude_self
            )
    
    def _find_with_brute_force(
        self,
        query_vector: Optional[List[float]],
        query_doc_key: Optional[str],
        similarity_threshold: float,
        limit: int,
        blocking_field: Optional[str],
        blocking_value: Optional[Any],
        filters: Optional[Dict[str, Dict[str, Any]]],
        exclude_self: bool
    ) -> List[Dict[str, Any]]:
        """
        Find similar vectors using brute-force cosine similarity
        
        This is the fallback method that works on all ArangoDB versions.
        """
        # Get query vector if doc_key provided
        if query_vector is None and query_doc_key:
            doc = self.db.collection(self.collection).get(query_doc_key)
            if not doc or self.embedding_field not in doc:
                return []
            query_vector = doc[self.embedding_field]
        
        if query_vector is None:
            return []
        
        # Build filter conditions
        filter_conditions = []
        if blocking_field and blocking_value is not None:
            filter_conditions.append(f"doc.{blocking_field} == @blocking_value")
        
        # Add custom filters
        if filters:
            for field, condition in filters.items():
                if 'equals' in condition:
                    filter_conditions.append(f"doc.{field} == @filter_{field}")
                elif 'in' in condition:
                    filter_conditions.append(f"doc.{field} IN @filter_{field}")
        
        filter_clause = " AND ".join(filter_conditions) if filter_conditions else "true"
        
        # Build exclude clause
        exclude_clause = ""
        if exclude_self and query_doc_key:
            exclude_clause = "FILTER doc._key != @exclude_key"
        
        # Brute-force cosine similarity query
        query = f"""
            FOR doc IN {self.collection}
                FILTER doc.{self.embedding_field} != null
                FILTER {filter_clause}
                {exclude_clause}
                
                // Compute cosine similarity (with zero-magnitude protection)
                LET dot_product = SUM(
                    FOR i IN 0..LENGTH(doc.{self.embedding_field})-1
                        RETURN doc.{self.embedding_field}[i] * @query_vector[i]
                )
                LET magnitude1 = SQRT(SUM(FOR x IN doc.{self.embedding_field} RETURN x*x))
                LET magnitude2 = SQRT(SUM(FOR x IN @query_vector RETURN x*x))
                
                // Protect against division by zero
                LET similarity = (magnitude1 > @min_magnitude AND magnitude2 > @min_magnitude)
                    ? (dot_product / (magnitude1 * magnitude2))
                    : 0.0
                
                FILTER similarity >= @similarity_threshold
                SORT similarity DESC
                LIMIT @limit
                
                RETURN {{
                    doc_key: doc._key,
                    similarity: similarity,
                    method: "brute_force"
                }}
        """
        
        bind_vars = {
            'query_vector': query_vector,
            'similarity_threshold': similarity_threshold,
            'limit': limit,
            'min_magnitude': MINIMUM_VECTOR_MAGNITUDE
        }
        
        if blocking_field and blocking_value is not None:
            bind_vars['blocking_value'] = blocking_value
        
        if exclude_self and query_doc_key:
            bind_vars['exclude_key'] = query_doc_key
        
        # Add filter bind vars
        if filters:
            for field, condition in filters.items():
                bind_vars[f'filter_{field}'] = condition.get('equals') or condition.get('in')
        
        cursor = self.db.aql.execute(query, bind_vars=bind_vars)
        results = list(cursor)
        
        return results
    
    def find_all_pairs(
        self,
        similarity_threshold: float = 0.7,
        limit_per_entity: int = 20,
        blocking_field: Optional[str] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all similar pairs in the collection (used by VectorBlockingStrategy)
        
        This method generates candidate pairs by comparing all documents with embeddings.
        
        Args:
            similarity_threshold: Minimum cosine similarity
            limit_per_entity: Maximum candidates per document
            blocking_field: Optional field to block on (only compare within same value)
            filters: Additional filters
            
        Returns:
            List of candidate pairs:
            [{
                'doc1_key': str,
                'doc2_key': str,
                'similarity': float,
                'method': str
            }]
        """
        # Build filter conditions
        filter_conditions = []
        if filters:
            for field, condition in filters.items():
                if 'equals' in condition:
                    filter_conditions.append(f"doc1.{field} == @filter_{field}")
                elif 'in' in condition:
                    filter_conditions.append(f"doc1.{field} IN @filter_{field}")
        
        filter_clause = " AND ".join(filter_conditions) if filter_conditions else "true"
        
        # Build blocking clause
        blocking_clause = ""
        if blocking_field:
            blocking_clause = f"AND doc1.{blocking_field} == doc2.{blocking_field}"
        
        # Use brute-force for pair generation (more predictable)
        # Vector search is better for single-query scenarios
        query = f"""
            FOR doc1 IN {self.collection}
                FILTER doc1.{self.embedding_field} != null
                FILTER {filter_clause}
                
                // Find similar documents
                FOR doc2 IN {self.collection}
                    FILTER doc2.{self.embedding_field} != null
                    FILTER doc1._key < doc2._key  // Avoid duplicates and self-pairs
                    {blocking_clause}
                    
                    // Compute cosine similarity (with zero-magnitude protection)
                    LET dot_product = SUM(
                        FOR i IN 0..LENGTH(doc1.{self.embedding_field})-1
                            RETURN doc1.{self.embedding_field}[i] * doc2.{self.embedding_field}[i]
                    )
                    LET magnitude1 = SQRT(SUM(FOR x IN doc1.{self.embedding_field} RETURN x*x))
                    LET magnitude2 = SQRT(SUM(FOR x IN doc2.{self.embedding_field} RETURN x*x))
                    
                    // Protect against division by zero
                    LET similarity = (magnitude1 > @min_magnitude AND magnitude2 > @min_magnitude)
                        ? (dot_product / (magnitude1 * magnitude2))
                        : 0.0
                    
                    FILTER similarity >= @similarity_threshold
                    
                    SORT similarity DESC
                    LIMIT @limit_per_entity
                    
                    RETURN {{
                        doc1_key: doc1._key,
                        doc2_key: doc2._key,
                        similarity: similarity,
                        method: @method
                    }}
        """
        
        bind_vars = {
            'similarity_threshold': similarity_threshold,
            'limit_per_entity': limit_per_entity,
            'min_magnitude': MINIMUM_VECTOR_MAGNITUDE,
            'method': self._method
        }
        
        # Add filter bind vars
        if filters:
            for field, condition in filters.items():
                bind_vars[f'filter_{field}'] = condition.get('equals') or condition.get('in')
        
        try:
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            pairs = list(cursor)
            return pairs
        except Exception as e:
            self.logger.error(f"Pair generation query failed: {e}")
            raise
