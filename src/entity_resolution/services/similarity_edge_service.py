"""
Similarity edge creation service.

This service creates edges between similar entities in bulk, with comprehensive
metadata for tracking and analysis. Optimized for high-throughput edge creation.
"""

from typing import List, Dict, Any, Optional, Tuple
from arango.database import StandardDatabase
from arango.collection import EdgeCollection
import time
from datetime import datetime
import logging

from ..utils.graph_utils import format_vertex_id
from ..utils.constants import DEFAULT_EDGE_BATCH_SIZE, DEFAULT_SIMILARITY_THRESHOLD


class SimilarityEdgeService:
    """
    Bulk creation of similarity edges with metadata.
    
    Creates edges between similar entities in batches, with comprehensive
    metadata for tracking and analysis. Provides high-throughput edge creation
    with proper error handling.
    
    Features:
    - Bulk edge insertion (batched for performance)
    - Deterministic edge keys (enabled by default) for idempotent pipelines
    - Automatic _from/_to formatting
    - Configurable metadata fields
    - Timestamp tracking
    - Method/algorithm tracking
    - Progress callbacks
    - SmartGraph compatible (works for both sharded and non-sharded)
    
    Performance: ~10K+ edges/second
    
    Example:
        ```python
        service = SimilarityEdgeService(
            db=db,
            edge_collection="similarTo",
            vertex_collection="companies",
            use_deterministic_keys=True  # Default - prevents duplicates
        )
        
        matches = [
            ("123", "456", 0.92),
            ("789", "012", 0.87)
        ]
        
        # Safe to run multiple times - no duplicates
        edges_created = service.create_edges(
            matches=matches,
            metadata={
                "method": "hybrid_blocking",
                "algorithm": "jaro_winkler",
                "threshold": 0.75
            }
        )
        ```
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        edge_collection: str = "similarTo",
        vertex_collection: Optional[str] = None,
        batch_size: int = DEFAULT_EDGE_BATCH_SIZE,
        auto_create_collection: bool = True,
        use_deterministic_keys: bool = True
    ):
        """
        Initialize similarity edge service.
        
        Args:
            db: ArangoDB database connection
            edge_collection: Edge collection name. Default "similarTo".
            vertex_collection: Vertex collection name for _from/_to formatting.
                If None, will use format "collection/{key}".
                If provided, will use "{vertex_collection}/{key}".
            batch_size: Edges to insert per batch. Default DEFAULT_EDGE_BATCH_SIZE (1000).
            auto_create_collection: Create edge collection if it doesn't exist.
                Default True.
            use_deterministic_keys: Generate deterministic edge keys based on _from/_to
                to prevent duplicate edges. Default True. When enabled, the same vertex
                pair will always generate the same edge key, and overwriteMode='ignore'
                is used to make edge creation idempotent. Works for both SmartGraph and
                non-SmartGraph deployments.
        
        Raises:
            ValueError: If configuration is invalid
        """
        self.db = db
        self.edge_collection_name = edge_collection
        self.vertex_collection = vertex_collection
        self.batch_size = batch_size
        self.use_deterministic_keys = use_deterministic_keys
        
        # Initialize logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Get or create edge collection
        if auto_create_collection and not db.has_collection(edge_collection):
            self.edge_collection = db.create_collection(edge_collection, edge=True)
        else:
            self.edge_collection: EdgeCollection = db.collection(edge_collection)
        
        # Statistics tracking
        self._stats = {
            'edges_created': 0,
            'batches_processed': 0,
            'avg_batch_size': 0,
            'execution_time_seconds': 0.0,
            'edges_per_second': 0,
            'timestamp': None
        }
    
    def create_edges(
        self,
        matches: List[Tuple[str, str, float]],
        metadata: Optional[Dict[str, Any]] = None,
        bidirectional: bool = False
    ) -> int:
        """
        Create similarity edges in bulk.
        
        Args:
            matches: List of (doc1_key, doc2_key, score) tuples
            metadata: Additional metadata to include in all edges:
                {
                    "method": "hybrid_blocking",
                    "algorithm": "jaro_winkler",
                    "threshold": DEFAULT_SIMILARITY_THRESHOLD,  # Default 0.75
                    "run_id": "run_20251112_143022"
                }
            bidirectional: If True, create edges in both directions.
                Default False (unidirectional edges).
        
        Returns:
            Number of edges created
        
        Performance: ~10K+ edges/second
        """
        if not matches:
            return 0
        
        start_time = time.time()
        edges_created = 0
        batch_count = 0
        
        # Prepare metadata
        edge_metadata = metadata or {}
        edge_metadata['timestamp'] = datetime.now().isoformat()
        
        # Insert in batches
        for i in range(0, len(matches), self.batch_size):
            batch = matches[i:i + self.batch_size]
            batch_edges = []
            
            for doc1_key, doc2_key, score in batch:
                # Format vertex IDs
                from_id = self._format_vertex_id(doc1_key)
                to_id = self._format_vertex_id(doc2_key)
                
                # Create primary edge
                edge = {
                    '_from': from_id,
                    '_to': to_id,
                    'similarity': round(score, 4),
                    **edge_metadata
                }
                
                # Add deterministic key if enabled
                if self.use_deterministic_keys:
                    edge['_key'] = self._generate_deterministic_key(from_id, to_id)
                
                batch_edges.append(edge)
                
                # Create reverse edge if bidirectional
                if bidirectional:
                    reverse_edge = {
                        '_from': to_id,
                        '_to': from_id,
                        'similarity': round(score, 4),
                        **edge_metadata
                    }
                    
                    # Add deterministic key for reverse edge if enabled
                    if self.use_deterministic_keys:
                        # Same key as forward edge (order-independent)
                        reverse_edge['_key'] = self._generate_deterministic_key(to_id, from_id)
                    
                    batch_edges.append(reverse_edge)
            
            # Insert batch
            if batch_edges:
                try:
                    # Use overwrite mode when deterministic keys are enabled
                    # This makes edge creation idempotent
                    overwrite_mode = 'ignore' if self.use_deterministic_keys else None
                    self.edge_collection.insert_many(batch_edges, overwrite_mode=overwrite_mode)
                    edges_created += len(batch_edges)
                    batch_count += 1
                except Exception as e:
                    # Log error but continue with other batches
                    self.logger.error(f"Failed to insert edge batch: {e}", exc_info=True)
        
        # Update statistics
        execution_time = time.time() - start_time
        self._update_statistics(edges_created, batch_count, execution_time)
        
        return edges_created
    
    def create_edges_detailed(
        self,
        matches: List[Dict[str, Any]],
        bidirectional: bool = False
    ) -> int:
        """
        Create edges with per-edge metadata.
        
        This method allows different metadata for each edge, useful when
        edges come from different methods or have different characteristics.
        
        Args:
            matches: List of detailed match records:
                [
                    {
                        "doc1_key": "123",
                        "doc2_key": "456",
                        "similarity": 0.87,
                        "field_scores": {...},
                        "blocking_method": "phone_state",
                        # ... any additional metadata
                    },
                    ...
                ]
            bidirectional: If True, create edges in both directions
        
        Returns:
            Number of edges created
        """
        if not matches:
            return 0
        
        start_time = time.time()
        edges_created = 0
        batch_count = 0
        
        # Insert in batches
        for i in range(0, len(matches), self.batch_size):
            batch = matches[i:i + self.batch_size]
            batch_edges = []
            
            for match in batch:
                doc1_key = match.get('doc1_key')
                doc2_key = match.get('doc2_key')
                
                if not doc1_key or not doc2_key:
                    continue
                
                # Format vertex IDs
                from_id = self._format_vertex_id(doc1_key)
                to_id = self._format_vertex_id(doc2_key)
                
                # Create edge with all metadata from match
                edge = {
                    '_from': from_id,
                    '_to': to_id,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Add deterministic key if enabled
                if self.use_deterministic_keys:
                    edge['_key'] = self._generate_deterministic_key(from_id, to_id)
                
                # Add all other fields from match (excluding keys)
                for key, value in match.items():
                    if key not in ('doc1_key', 'doc2_key'):
                        edge[key] = value
                
                batch_edges.append(edge)
                
                # Create reverse edge if bidirectional
                if bidirectional:
                    reverse_edge = {
                        '_from': to_id,
                        '_to': from_id,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Add deterministic key for reverse edge if enabled
                    if self.use_deterministic_keys:
                        # Same key as forward edge (order-independent)
                        reverse_edge['_key'] = self._generate_deterministic_key(to_id, from_id)
                    
                    for key, value in match.items():
                        if key not in ('doc1_key', 'doc2_key'):
                            reverse_edge[key] = value
                    batch_edges.append(reverse_edge)
            
            # Insert batch
            if batch_edges:
                try:
                    # Use overwrite mode when deterministic keys are enabled
                    overwrite_mode = 'ignore' if self.use_deterministic_keys else None
                    self.edge_collection.insert_many(batch_edges, overwrite_mode=overwrite_mode)
                    edges_created += len(batch_edges)
                    batch_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to insert edge batch: {e}", exc_info=True)
        
        # Update statistics
        execution_time = time.time() - start_time
        self._update_statistics(edges_created, batch_count, execution_time)
        
        return edges_created
    
    def clear_edges(
        self,
        method: Optional[str] = None,
        older_than: Optional[str] = None
    ) -> int:
        """
        Clear similarity edges.
        
        Useful for iterative workflows where you want to clear previous
        results before running a new ER pipeline.
        
        Args:
            method: Only clear edges with this method (optional).
                If None, clears all edges.
            older_than: Only clear edges older than this ISO timestamp (optional)
        
        Returns:
            Number of edges removed
        
        Example:
            ```python
            # Clear all edges
            service.clear_edges()
            
            # Clear only edges from specific method
            service.clear_edges(method="phone_blocking")
            
            # Clear edges older than a date
            service.clear_edges(older_than="2025-01-01T00:00:00")
            ```
        """
        query_parts = [f"FOR e IN {self.edge_collection_name}"]
        filters = []
        
        if method:
            filters.append(f'FILTER e.method == "{method}"')
        
        if older_than:
            filters.append(f'FILTER e.timestamp < "{older_than}"')
        
        query_parts.extend(filters)
        query_parts.append("REMOVE e IN " + self.edge_collection_name)
        query_parts.append("RETURN OLD")
        
        query = "\n    ".join(query_parts)
        
        cursor = self.db.aql.execute(query)
        removed = list(cursor)
        
        return len(removed)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get edge creation statistics.
        
        Returns:
            Statistics dictionary:
            {
                "edges_created": 12345,
                "batches_processed": 13,
                "avg_batch_size": 949,
                "execution_time_seconds": 1.2,
                "edges_per_second": 10287,
                "timestamp": "2025-11-12T14:30:22"
            }
        """
        return self._stats.copy()
    
    def _format_vertex_id(self, key: str) -> str:
        """
        Format a document key as a vertex ID for edge _from/_to.
        
        Args:
            key: Document key
        
        Returns:
            Formatted vertex ID: "collection/key"
        
        Note:
            This method now delegates to the shared graph_utils.format_vertex_id()
            for consistency across the codebase.
        """
        return format_vertex_id(key, self.vertex_collection)
    
    def _generate_deterministic_key(self, from_id: str, to_id: str) -> str:
        """
        Generate deterministic edge key from vertex IDs.
        
        This ensures the same pair of vertices always generates the same edge key,
        preventing duplicate edges when the pipeline runs multiple times.
        
        Works for both SmartGraph and non-SmartGraph deployments:
        - Non-SmartGraph: from_id = "collection/key"
        - SmartGraph: from_id = "collection/shard:key"
        
        The implementation simply hashes the full _id values. ArangoDB automatically
        handles edge placement based on the _from field, so no special SmartGraph
        logic is needed in the edge key.
        
        Args:
            from_id: Full document ID for _from vertex (e.g., "duns/12345" or "duns/570:12345")
            to_id: Full document ID for _to vertex
        
        Returns:
            Deterministic edge key (MD5 hash)
        
        Example:
            >>> _generate_deterministic_key("duns/123", "duns/456")
            "a1b2c3d4e5f6..."  # MD5 hash
            
            >>> _generate_deterministic_key("duns/570:123", "duns/570:456")  # SmartGraph
            "x1y2z3w4a5b6..."  # Different hash, but still deterministic
        """
        import hashlib
        
        # Ensure consistent ordering (order-independent hash)
        # This way (A, B) and (B, A) produce the same key
        if from_id < to_id:
            key_string = f"{from_id}->{to_id}"
        else:
            key_string = f"{to_id}->{from_id}"
        
        # Generate MD5 hash (sufficient for uniqueness, not for security)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def _update_statistics(
        self,
        edges_created: int,
        batches_processed: int,
        execution_time: float
    ):
        """Update internal statistics."""
        avg_batch_size = edges_created / batches_processed if batches_processed > 0 else 0
        
        self._stats.update({
            'edges_created': edges_created,
            'batches_processed': batches_processed,
            'avg_batch_size': int(avg_batch_size),
            'execution_time_seconds': round(execution_time, 2),
            'edges_per_second': int(edges_created / execution_time) if execution_time > 0 else 0,
            'timestamp': datetime.now().isoformat()
        })
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"SimilarityEdgeService("
                f"edge_collection='{self.edge_collection_name}', "
                f"batch_size={self.batch_size})")

