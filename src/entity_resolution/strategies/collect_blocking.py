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
        computed_fields: Optional[Dict[str, str]] = None,
        exclude_values: Optional[Dict[str, set]] = None
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
                Dictionary mapping computed field names to AQL expressions.
                Example: {"zip5": "LEFT(d.postal_code, 5)"}
                These computed field names can then be used in blocking_fields.
                
                Note: In expressions, reference document fields as "d.field_name".
                In blocking_fields and filters, reference computed fields by name only.
            exclude_values: Optional set of known-bad values to exclude from
                blocking, keyed by field name. Documents matching any excluded
                value are dropped before COLLECT grouping. Useful for removing
                hub addresses (registered agent offices, co-working spaces) or
                placeholder strings that would create false-positive blocks.
                Example: {"address": {"401 E 8TH STREET", "300 N DAKOTA AVE"}}
        
        Examples:
            Basic phone + state blocking:
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
            
            Address blocking with hub address exclusion:
            ```python
            strategy = CollectBlockingStrategy(
                db=db,
                collection="companies",
                blocking_fields=["address", "zip5"],
                computed_fields={"zip5": "LEFT(d.postal_code, 5)"},
                exclude_values={
                    "address": {"401 E 8TH STREET", "300 N DAKOTA AVE"}
                },
                max_block_size=50,
                min_block_size=2
            )
            pairs = strategy.generate_candidates()
            ```
        """
        super().__init__(db, collection, filters)
        
        # Store computed fields first so we can reference them during validation
        self.computed_fields = computed_fields or {}
        
        # Validate inputs
        if not blocking_fields:
            raise ValueError("blocking_fields cannot be empty")
        
        # Validate field names for security (prevent AQL injection)
        # Skip validation for computed field names (they're validated separately)
        non_computed_fields = [f for f in blocking_fields if f not in self.computed_fields]
        if non_computed_fields:
            validate_field_names(non_computed_fields)
        
        # Validate computed field names (variable names, not expressions)
        for computed_field_name in self.computed_fields.keys():
            if not computed_field_name.replace('_', '').isalnum():
                raise ValueError(
                    f"Computed field name '{computed_field_name}' must be alphanumeric "
                    f"(underscores allowed)"
                )
            if computed_field_name[0].isdigit():
                raise ValueError(
                    f"Computed field name '{computed_field_name}' cannot start with a digit"
                )
        
        self.blocking_fields = blocking_fields
        self.max_block_size = max_block_size
        self.min_block_size = min_block_size
        self.exclude_values = exclude_values or {}
        
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
        query, bind_vars = self._build_collect_query()

        # Execute query
        cursor = self.db.aql.execute(query, bind_vars=bind_vars)
        pairs = list(cursor)
        
        # Normalize pairs
        normalized_pairs = self._normalize_pairs(pairs)
        
        # Update statistics
        execution_time = time.time() - start_time
        self._update_statistics(normalized_pairs, execution_time)
        
        # Add additional stats
        exclude_counts = {k: len(v) for k, v in self.exclude_values.items() if v}
        self._stats.update({
            'blocking_fields': self.blocking_fields,
            'min_block_size': self.min_block_size,
            'max_block_size': self.max_block_size,
            'blocks_processed': self._estimate_blocks_processed(normalized_pairs),
            'excluded_value_counts': exclude_counts
        })
        
        return normalized_pairs
    
    def _build_filter_conditions(
        self,
        field_filters: Dict[str, Any],
        computed_field_map: Optional[Dict[str, str]] = None,
    ) -> tuple[list[str], dict]:
        """
        Build AQL filter conditions, handling both document fields and computed fields.

        Overrides base implementation to support computed fields.
        String values are placed in bind vars to prevent AQL injection (C2).

        Returns:
            A 2-tuple of (conditions list, bind_vars dict).
        """
        conditions: list[str] = []
        bind_vars: dict = {}
        computed_field_map = computed_field_map or {}

        for field_name, filters in field_filters.items():
            if not isinstance(filters, dict):
                continue

            # Determine if this is a computed field and get the correct reference
            if field_name in computed_field_map:
                field_ref = computed_field_map[field_name]
            elif field_name in self.computed_fields:
                field_ref = field_name
            else:
                field_ref = f"d.{field_name}"

            # Not null filter
            if filters.get('not_null'):
                conditions.append(f"{field_ref} != null")

            # Not equal filter (list of values to exclude)
            if 'not_equal' in filters:
                not_equal_values = filters['not_equal']
                if isinstance(not_equal_values, list):
                    for i, value in enumerate(not_equal_values):
                        var = f"_ne_{field_name}_{i}"
                        bind_vars[var] = value
                        conditions.append(f"{field_ref} != @{var}")

            # Equals filter
            if 'equals' in filters:
                var = f"_eq_{field_name}"
                bind_vars[var] = filters['equals']
                conditions.append(f"{field_ref} == @{var}")

            # Min length filter
            if 'min_length' in filters:
                conditions.append(f"LENGTH({field_ref}) >= {int(filters['min_length'])}")

            # Max length filter
            if 'max_length' in filters:
                conditions.append(f"LENGTH({field_ref}) <= {int(filters['max_length'])}")

            # Contains filter
            if 'contains' in filters:
                var = f"_contains_{field_name}"
                bind_vars[var] = filters['contains']
                conditions.append(f"CONTAINS({field_ref}, @{var})")

            # Regex filter
            if 'regex' in filters:
                var = f"_regex_{field_name}"
                bind_vars[var] = filters['regex']
                conditions.append(f"REGEX_TEST({field_ref}, @{var})")

        return conditions, bind_vars
    
    def _build_collect_query(self) -> tuple[str, dict]:
        """
        Build the AQL query for COLLECT-based blocking.

        Returns:
            A 2-tuple of (AQL query string, bind_vars dict).
        """
        # Start building query
        query_parts = [f"FOR d IN {self.collection}"]

        # Add computed fields with temporary variable names to avoid COLLECT conflicts
        computed_field_map = {}
        for field_name, expression in self.computed_fields.items():
            temp_var = f"_computed_{field_name}"
            query_parts.append(f"    LET {temp_var} = {expression}")
            computed_field_map[field_name] = temp_var

        bind_vars: dict = {}
        # Add filter conditions
        if self.filters:
            conditions, filter_bind_vars = self._build_filter_conditions(self.filters, computed_field_map)
            bind_vars.update(filter_bind_vars)
            for condition in conditions:
                query_parts.append(f"    FILTER {condition}")

        # Add exclusion filters for known hub/bad values
        for field_name, values_set in self.exclude_values.items():
            if not values_set:
                continue
            bind_key = f"_excl_{field_name}"
            bind_vars[bind_key] = sorted(values_set)
            if field_name in computed_field_map:
                field_ref = computed_field_map[field_name]
            else:
                field_ref = f"d.{field_name}"
            query_parts.append(f"    FILTER {field_ref} NOT IN @{bind_key}")

        # Build COLLECT clause
        collect_vars = []
        for field in self.blocking_fields:
            if field in self.computed_fields:
                temp_var = computed_field_map[field]
                collect_vars.append(f"{field} = {temp_var}")
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

        return "\n".join(query_parts), bind_vars
    
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

