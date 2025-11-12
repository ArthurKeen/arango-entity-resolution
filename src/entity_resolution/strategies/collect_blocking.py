"""
COLLECT-based blocking strategy.

This strategy uses ArangoDB's COLLECT operation to group documents by
composite blocking keys, then generates candidate pairs only within small blocks.
This avoids expensive cartesian products and provides O(n) complexity.
"""

from typing import List, Dict, Any, Optional
from arango.database import StandardDatabase
import time

from .base_strategy import BlockingStrategy
from ..utils.validation import validate_field_names


class CollectBlockingStrategy(BlockingStrategy):
    """
    COLLECT-based blocking for efficient composite key matching.
    
    Uses ArangoDB's COLLECT operation to group documents by blocking keys,
    then generates candidate pairs only within small blocks. This approach:
    - Avoids expensive cartesian products
    - Provides O(n) complexity where n = number of documents
    - Scales efficiently to hundreds of thousands of records
    - Supports composite keys (multiple fields combined)
    
    Example use cases:
    - Phone + State blocking
    - CEO Name + State blocking
    - Address + Zip code blocking
    - Any combination of exact-match fields
    
    Performance: Can process 300K+ documents in seconds
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        blocking_fields: List[str],
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
        max_block_size: int = 100,
        min_block_size: int = 2,
        computed_fields: Optional[Dict[str, str]] = None
    ):
        """
        Initialize COLLECT-based blocking strategy.
        
        Args:
            db: ArangoDB database connection
            collection: Source collection name
            blocking_fields: List of fields to use as composite blocking key.
                Example: ["phone", "state"] or ["ceo_name", "state"]
            filters: Optional filters per field (see base class for format)
            max_block_size: Skip blocks larger than this (likely bad data or
                common values). Default 100.
            min_block_size: Skip blocks smaller than this (no pairs to generate).
                Default 2.
            computed_fields: Optional computed fields for blocking.
                Example: {"zip5": "LEFT(postal_code, 5)"}
                These can be used in blocking_fields.
        
        Example:
            ```python
            strategy = CollectBlockingStrategy(
                db=db,
                collection="companies",
                blocking_fields=["phone", "state"],
                filters={
                    "phone": {
                        "not_null": True,
                        "min_length": 10,
                        "not_equal": ["0", "00000000000"]
                    },
                    "state": {"not_null": True}
                },
                max_block_size=100,
                min_block_size=2
            )
            pairs = strategy.generate_candidates()
            ```
        """
        super().__init__(db, collection, filters)
        
        # Validate inputs first
        if not blocking_fields:
            raise ValueError("blocking_fields cannot be empty")
        
        # Validate field names for security (prevent AQL injection)
        self.blocking_fields = validate_field_names(blocking_fields)
        self.max_block_size = max_block_size
        self.min_block_size = min_block_size
        self.computed_fields = computed_fields or {}
        if min_block_size < 2:
            raise ValueError("min_block_size must be at least 2")
        if max_block_size < min_block_size:
            raise ValueError("max_block_size must be >= min_block_size")
    
    def generate_candidates(self) -> List[Dict[str, Any]]:
        """
        Generate candidate pairs using COLLECT-based blocking.
        
        Process:
        1. Apply filters to documents
        2. Compute any derived fields
        3. COLLECT documents by blocking keys
        4. For each block (of reasonable size):
           - Generate all pairs within the block
        5. Return candidate pairs with metadata
        
        Returns:
            List of candidate pairs:
            [
                {
                    "doc1_key": "123",
                    "doc2_key": "456",
                    "blocking_keys": {"phone": "5551234567", "state": "CA"},
                    "block_size": 3,
                    "method": "collect_blocking"
                },
                ...
            ]
        
        Performance: O(n) where n = number of documents
        """
        start_time = time.time()
        
        # Build the AQL query
        query = self._build_collect_query()
        
        # Execute query
        cursor = self.db.aql.execute(query)
        pairs = list(cursor)
        
        # Normalize pairs
        normalized_pairs = self._normalize_pairs(pairs)
        
        # Update statistics
        execution_time = time.time() - start_time
        self._update_statistics(normalized_pairs, execution_time)
        
        # Add additional stats
        self._stats.update({
            'blocking_fields': self.blocking_fields,
            'min_block_size': self.min_block_size,
            'max_block_size': self.max_block_size,
            'blocks_processed': self._estimate_blocks_processed(normalized_pairs)
        })
        
        return normalized_pairs
    
    def _build_collect_query(self) -> str:
        """
        Build the AQL query for COLLECT-based blocking.
        
        Returns:
            AQL query string
        """
        # Start building query
        query_parts = [f"FOR d IN {self.collection}"]
        
        # Add computed fields
        for field_name, expression in self.computed_fields.items():
            query_parts.append(f"    LET {field_name} = {expression}")
        
        # Add filter conditions
        if self.filters:
            conditions = self._build_filter_conditions(self.filters)
            for condition in conditions:
                query_parts.append(f"    FILTER {condition}")
        
        # Build COLLECT clause
        collect_vars = []
        for field in self.blocking_fields:
            # Check if it's a computed field
            if field in self.computed_fields:
                collect_vars.append(f"{field} = {field}")
            else:
                collect_vars.append(f"{field} = d.{field}")
        
        collect_clause = f"    COLLECT {', '.join(collect_vars)}"
        query_parts.append(collect_clause)
        
        # Add INTO clause to keep documents
        query_parts.append("    INTO group")
        query_parts.append("    KEEP d")
        
        # Extract document keys
        query_parts.append("    LET doc_keys = group[*].d._key")
        
        # Filter by block size
        query_parts.append(f"    FILTER LENGTH(doc_keys) >= {self.min_block_size}")
        query_parts.append(f"    FILTER LENGTH(doc_keys) <= {self.max_block_size}")
        
        # Generate pairs within block
        query_parts.append("    FOR i IN 0..LENGTH(doc_keys)-2")
        query_parts.append("        FOR j IN (i+1)..LENGTH(doc_keys)-1")
        
        # Build return object with blocking key values
        blocking_key_obj = []
        for field in self.blocking_fields:
            blocking_key_obj.append(f'"{field}": {field}')
        
        return_clause = f"""            RETURN {{
                doc1_key: doc_keys[i],
                doc2_key: doc_keys[j],
                blocking_keys: {{{', '.join(blocking_key_obj)}}},
                block_size: LENGTH(doc_keys),
                method: "collect_blocking"
            }}"""
        
        query_parts.append(return_clause)
        
        return "\n".join(query_parts)
    
    def _estimate_blocks_processed(self, pairs: List[Dict[str, Any]]) -> int:
        """
        Estimate number of blocks processed from pair count.
        
        This is approximate since we don't track exact block counts.
        
        Args:
            pairs: List of generated pairs
        
        Returns:
            Estimated number of blocks
        """
        # Extract unique block sizes from pairs
        if not pairs:
            return 0
        
        # Group pairs by their blocking keys to estimate blocks
        block_signatures = set()
        for pair in pairs:
            if 'blocking_keys' in pair:
                # Create a hashable signature from blocking keys
                keys = tuple(sorted(pair['blocking_keys'].items()))
                block_signatures.add(keys)
        
        return len(block_signatures)
    
    def __repr__(self) -> str:
        """String representation of the strategy."""
        fields_str = ', '.join(self.blocking_fields)
        return (f"CollectBlockingStrategy("
                f"collection='{self.collection}', "
                f"blocking_fields=[{fields_str}], "
                f"block_size={self.min_block_size}-{self.max_block_size})")

