"""
Vector Blocking Strategy for Entity Resolution

Uses vector embeddings and cosine similarity to find candidate pairs based on
semantic similarity. This is a Tier 3 blocking strategy that can capture fuzzy
matches missed by exact (Tier 1) or text-based (Tier 2) blocking.

Based on research:
- Ebraheem et al. (2018): "Distributed Representations of Tuples for Entity Resolution"
- Uses pre-trained sentence-transformers embeddings
- Performs approximate nearest neighbor (ANN) search via ArangoDB

Implementation Strategy:
- Assumes embeddings are already stored in documents (use EmbeddingService first)
- Uses AQL with vector similarity functions
- Configurable similarity threshold and candidate limit
- Optional blocking field for additional filtering (e.g., geography, category)
"""

import logging
import time
from typing import List, Dict, Any, Optional
from arango.database import StandardDatabase
import numpy as np

from .base_strategy import BlockingStrategy
from ..utils.validation import validate_collection_name, validate_field_name
from ..utils.aql_builders import build_aql_filter_conditions
from ..similarity.ann_adapter import ANNAdapter


# Constants for vector blocking configuration  
DEFAULT_EMBEDDING_FIELD = 'embedding_vector'
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_LIMIT_PER_ENTITY = 20
MINIMUM_VECTOR_MAGNITUDE = 1e-10  # Prevent division by zero


class VectorBlockingStrategy(BlockingStrategy):
    """
    Vector-based blocking using cosine similarity
    
    Generates candidate pairs by finding documents with similar vector embeddings.
    This enables semantic similarity matching that goes beyond exact text matching.
    
    Prerequisites:
    - Documents must have pre-computed embeddings (use EmbeddingService)
    - Embeddings should be stored in the specified embedding_field
    
    Attributes:
        embedding_field: Field name containing vector embeddings
        similarity_threshold: Minimum cosine similarity (0-1) to consider a match
        limit_per_entity: Maximum candidates per document
        blocking_field: Optional field for additional blocking (e.g., state, category)
    
    Example:
        >>> from entity_resolution.services.embedding_service import EmbeddingService
        >>> from entity_resolution.strategies.vector_blocking import VectorBlockingStrategy
        >>> 
        >>> # First, ensure embeddings exist
        >>> embedding_service = EmbeddingService()
        >>> embedding_service.ensure_embeddings_exist(
        ...     'customers',
        ...     text_fields=['name', 'company', 'address']
        ... )
        >>> 
        >>> # Then use vector blocking
        >>> strategy = VectorBlockingStrategy(
        ...     db=db,
        ...     collection='customers',
        ...     similarity_threshold=0.7,
        ...     limit_per_entity=20
        ... )
        >>> pairs = strategy.generate_candidates()
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        embedding_field: str = DEFAULT_EMBEDDING_FIELD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        limit_per_entity: int = DEFAULT_LIMIT_PER_ENTITY,
        blocking_field: Optional[str] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
        use_ann_adapter: bool = True,
        force_brute_force: bool = False
    ):
        """
        Initialize vector blocking strategy
        
        Args:
            db: ArangoDB database connection
            collection: Source collection name
            embedding_field: Field name containing embeddings (default: 'embedding_vector')
            similarity_threshold: Minimum cosine similarity (default: 0.7)
                - 0.9-1.0: Very similar (likely duplicates)
                - 0.8-0.9: Similar (possible duplicates)
                - 0.7-0.8: Somewhat similar (candidates)
                - Below 0.7: Low similarity
            limit_per_entity: Max candidates per document (default: 20)
            blocking_field: Optional field to block on (e.g., 'state', 'category')
                If provided, only compares documents with matching blocking_field values
            filters: Optional filters to apply before blocking
            use_ann_adapter: If True, use ANN adapter for optimized search (default: True)
            force_brute_force: If True, force brute-force mode (for testing/comparison)
            
        Raises:
            ValueError: If similarity_threshold not in range [0, 1]
            ValueError: If limit_per_entity < 1
        """
        super().__init__(db, collection, filters)
        
        if not 0 <= similarity_threshold <= 1:
            raise ValueError(
                f"similarity_threshold must be in [0, 1], got {similarity_threshold}"
            )
        
        if limit_per_entity < 1:
            raise ValueError(
                f"limit_per_entity must be >= 1, got {limit_per_entity}"
            )
        
        self.embedding_field = validate_field_name(embedding_field)
        self.similarity_threshold = similarity_threshold
        self.limit_per_entity = limit_per_entity
        self.blocking_field = validate_field_name(blocking_field) if blocking_field else None
        self.use_ann_adapter = use_ann_adapter
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize ANN adapter if requested
        if self.use_ann_adapter:
            self.ann_adapter = ANNAdapter(
                db=db,
                collection=collection,
                embedding_field=embedding_field,
                force_brute_force=force_brute_force
            )
        else:
            self.ann_adapter = None
        
        # Additional stats specific to vector blocking
        self._stats['embedding_field'] = self.embedding_field
        self._stats['similarity_threshold'] = self.similarity_threshold
        self._stats['limit_per_entity'] = self.limit_per_entity
        self._stats['blocking_field'] = self.blocking_field
        if self.ann_adapter:
            self._stats['ann_method'] = self.ann_adapter.method
    
    def _check_embeddings_exist(self) -> Dict[str, Any]:
        """
        Check if embeddings exist in the collection
        
        Returns:
            Dictionary with statistics about embedding coverage
        """
        query = f"""
            LET total = COUNT(FOR doc IN {self.collection} RETURN 1)
            LET with_embeddings = COUNT(
                FOR doc IN {self.collection}
                FILTER doc.{self.embedding_field} != null
                RETURN 1
            )
            RETURN {{
                total: total,
                with_embeddings: with_embeddings,
                without_embeddings: total - with_embeddings,
                coverage_percent: with_embeddings / total * 100
            }}
        """
        
        cursor = self.db.aql.execute(query)
        stats = cursor.next()
        
        return stats
    
    def generate_candidates(self) -> List[Dict[str, Any]]:
        """
        Generate candidate pairs using vector similarity
        
        Algorithm:
        1. For each document with embeddings
        2. Compute cosine similarity with all other documents
        3. Return pairs where similarity >= threshold
        4. Limit results per document to avoid explosion
        5. Normalize pairs to avoid duplicates (doc1_key < doc2_key)
        
        Returns:
            List of candidate pairs:
            [{
                'doc1_key': str,
                'doc2_key': str,
                'similarity': float,  # Cosine similarity score
                'method': 'vector'
            }]
            
        Raises:
            RuntimeError: If no embeddings found in collection
        """
        start_time = time.time()
        
        # Check embedding coverage
        embedding_stats = self._check_embeddings_exist()
        
        if embedding_stats['with_embeddings'] == 0:
            raise RuntimeError(
                f"No embeddings found in collection '{self.collection}'. "
                f"Use EmbeddingService.ensure_embeddings_exist() first."
            )
        
        if embedding_stats['coverage_percent'] < 100:
            self.logger.warning(
                f"Only {embedding_stats['coverage_percent']:.1f}% of documents "
                f"have embeddings ({embedding_stats['with_embeddings']}/{embedding_stats['total']})"
            )
        
        self.logger.info(
            f"Generating vector-based candidates with threshold={self.similarity_threshold}, "
            f"limit={self.limit_per_entity}"
        )
        
        # Use ANN adapter if enabled, otherwise use legacy method
        if self.use_ann_adapter and self.ann_adapter:
            try:
                pairs = self.ann_adapter.find_all_pairs(
                    similarity_threshold=self.similarity_threshold,
                    limit_per_entity=self.limit_per_entity,
                    blocking_field=self.blocking_field,
                    filters=self.filters
                )
            except Exception as e:
                self.logger.warning(
                    f"ANN adapter failed, falling back to legacy method: {e}"
                )
                pairs = self._generate_candidates_legacy()
        else:
            pairs = self._generate_candidates_legacy()
        
        # Normalize pairs (remove duplicates)
        pairs = self._normalize_pairs(pairs)
        
        execution_time = time.time() - start_time
        
        # Update statistics
        self._update_statistics(pairs, execution_time)
        self._stats['embedding_coverage_percent'] = embedding_stats['coverage_percent']
        self._stats['documents_with_embeddings'] = embedding_stats['with_embeddings']
        
        self.logger.info(
            f"Generated {len(pairs)} candidate pairs in {execution_time:.2f}s"
        )
        
        return pairs
    
    def _generate_candidates_legacy(self) -> List[Dict[str, Any]]:
        """
        Legacy brute-force candidate generation (backward compatibility)
        
        This method maintains the original implementation for compatibility.
        """
        # Build filter conditions
        filter_conditions, filter_bind_vars = build_aql_filter_conditions(
            self.filters,
            var_name="doc1",
            bind_var_prefix="filter",
        )
        filter_clause = " AND ".join(filter_conditions) if filter_conditions else "true"
        
        # Build blocking clause
        if self.blocking_field:
            blocking_clause = f"AND doc1.{self.blocking_field} == doc2.{self.blocking_field}"
        else:
            blocking_clause = ""
        
        # AQL query for vector similarity
        # Note: ArangoDB's built-in vector search depends on version
        # This implementation uses a simpler approach that works across versions
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
                    
                    // Protect against division by zero (zero-magnitude vectors)
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
                        method: "vector"
                    }}
        """
        
        # Execute query with bind variables for all user inputs
        bind_vars = {
            'similarity_threshold': self.similarity_threshold,
            'limit_per_entity': self.limit_per_entity,
            'min_magnitude': MINIMUM_VECTOR_MAGNITUDE
        }
        bind_vars.update(filter_bind_vars)
        
        try:
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            pairs = list(cursor)
        except Exception as e:
            self.logger.error(f"Vector blocking query failed: {e}")
            raise
        
        return pairs
    
    def generate_candidates_optimized(self) -> List[Dict[str, Any]]:
        """
        Optimized candidate generation using ArangoSearch (if available)
        
        This method uses ArangoSearch with vector analyzers for faster similarity search.
        Requires ArangoDB 3.10+ with proper view configuration.
        
        Note: This is an advanced optimization. Use generate_candidates() for compatibility.
        
        Returns:
            List of candidate pairs (same format as generate_candidates)
            
        Raises:
            NotImplementedError: If ArangoSearch view not configured
        """
        # This is a placeholder for future optimization
        # Requires creating an ArangoSearch view with vector analyzer
        raise NotImplementedError(
            "Optimized vector search requires ArangoSearch view configuration. "
            "See documentation for setup instructions, or use generate_candidates() "
            "for the compatibility version."
        )
    
    def get_similarity_distribution(self, sample_size: int = 1000) -> Dict[str, Any]:
        """
        Analyze similarity score distribution in the collection
        
        Useful for tuning the similarity_threshold parameter.
        
        Args:
            sample_size: Number of random pairs to sample
            
        Returns:
            Dictionary with distribution statistics:
            - min/max/mean/median similarity
            - Distribution by similarity bucket
            - Recommended thresholds
        """
        query = f"""
            FOR doc1 IN {self.collection}
                FILTER doc1.{self.embedding_field} != null
                LIMIT @sample_size
                
                LET doc2 = (
                    FOR d IN {self.collection}
                        FILTER d.{self.embedding_field} != null
                        FILTER d._key != doc1._key
                        LIMIT 1
                        RETURN d
                )[0]
                
                FILTER doc2 != null
                
                LET similarity = (
                    SUM(
                        FOR i IN 0..LENGTH(doc1.{self.embedding_field})-1
                            RETURN doc1.{self.embedding_field}[i] * doc2.{self.embedding_field}[i]
                    ) /
                    (
                        SQRT(SUM(FOR x IN doc1.{self.embedding_field} RETURN x*x)) *
                        SQRT(SUM(FOR x IN doc2.{self.embedding_field} RETURN x*x))
                    )
                )
                
                COLLECT bucket = FLOOR(similarity * 10) / 10 WITH COUNT INTO count
                RETURN {{bucket: bucket, count: count}}
        """
        
        cursor = self.db.aql.execute(query, bind_vars={'sample_size': sample_size})
        distribution = list(cursor)
        
        if not distribution:
            return {
                'error': 'No valid pairs found for analysis',
                'sample_size': sample_size
            }
        
        # Calculate statistics
        all_similarities = []
        for bucket in distribution:
            # Approximate: use bucket midpoint
            midpoint = bucket['bucket'] + 0.05
            all_similarities.extend([midpoint] * bucket['count'])
        
        all_similarities = np.array(all_similarities)
        
        return {
            'sample_size': len(all_similarities),
            'min_similarity': float(np.min(all_similarities)),
            'max_similarity': float(np.max(all_similarities)),
            'mean_similarity': float(np.mean(all_similarities)),
            'median_similarity': float(np.median(all_similarities)),
            'std_similarity': float(np.std(all_similarities)),
            'distribution': distribution,
            'recommended_thresholds': {
                'conservative': float(np.percentile(all_similarities, 90)),  # Top 10%
                'balanced': float(np.percentile(all_similarities, 75)),      # Top 25%
                'aggressive': float(np.percentile(all_similarities, 50))     # Top 50%
            }
        }
    
    def __repr__(self) -> str:
        """String representation of the strategy"""
        return (
            f"VectorBlockingStrategy(collection='{self.collection}', "
            f"threshold={self.similarity_threshold}, "
            f"limit={self.limit_per_entity})"
        )

