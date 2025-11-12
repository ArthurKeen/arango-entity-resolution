"""
Base blocking strategy class.

All blocking strategies inherit from this abstract base class to ensure
consistent API and behavior.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from arango.database import StandardDatabase
import time
from datetime import datetime

from ..utils.validation import validate_collection_name


class BlockingStrategy(ABC):
    """
    Abstract base class for all blocking strategies.
    
    A blocking strategy generates candidate pairs of documents that are likely
    to represent the same entity. Different strategies use different criteria
    to identify candidates (e.g., exact field matches, fuzzy matching, etc.).
    
    All blocking strategies should:
    - Accept database and collection as configuration
    - Provide configurable filters
    - Return standardized candidate pair format
    - Track statistics about the blocking process
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        filters: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        """
        Initialize base blocking strategy.
        
        Args:
            db: ArangoDB database connection
            collection: Source collection name to generate candidates from
            filters: Optional filters to apply to documents before blocking.
                Format: {
                    "field_name": {
                        "not_null": True,
                        "not_equal": ["value1", "value2"],
                        "min_length": 5,
                        "max_length": 100,
                        "equals": "value",
                        "contains": "substring",
                        "regex": "pattern"
                    }
                }
        """
        self.db = db
        self.collection = validate_collection_name(collection)
        self.filters = filters or {}
        
        # Statistics tracking
        self._stats = {
            'total_pairs': 0,
            'execution_time_seconds': 0.0,
            'strategy_name': self.__class__.__name__,
            'timestamp': None
        }
    
    @abstractmethod
    def generate_candidates(self) -> List[Dict[str, Any]]:
        """
        Generate candidate pairs using this blocking strategy.
        
        This method must be implemented by all concrete blocking strategies.
        
        Returns:
            List of candidate pairs with metadata. Each pair should include:
            {
                "doc1_key": str,  # Key of first document
                "doc2_key": str,  # Key of second document
                # Additional strategy-specific metadata
            }
        
        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError("Subclasses must implement generate_candidates()")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the most recent blocking operation.
        
        Returns:
            Dictionary containing:
            - total_pairs: Number of candidate pairs generated
            - execution_time_seconds: Time taken to generate pairs
            - strategy_name: Name of the blocking strategy used
            - timestamp: When the blocking was performed
            - Additional strategy-specific statistics
        """
        return self._stats.copy()
    
    def _build_filter_conditions(self, field_filters: Dict[str, Any]) -> List[str]:
        """
        Build AQL filter conditions from filter specification.
        
        Args:
            field_filters: Filter specifications for fields
        
        Returns:
            List of AQL filter condition strings
        """
        conditions = []
        
        for field_name, filters in field_filters.items():
            if not isinstance(filters, dict):
                continue
            
            # Not null filter
            if filters.get('not_null'):
                conditions.append(f"d.{field_name} != null")
            
            # Not equal filter (list of values to exclude)
            if 'not_equal' in filters:
                not_equal_values = filters['not_equal']
                if isinstance(not_equal_values, list):
                    for value in not_equal_values:
                        if isinstance(value, str):
                            conditions.append(f'd.{field_name} != "{value}"')
                        else:
                            conditions.append(f'd.{field_name} != {value}')
            
            # Equals filter
            if 'equals' in filters:
                value = filters['equals']
                if isinstance(value, str):
                    conditions.append(f'd.{field_name} == "{value}"')
                else:
                    conditions.append(f'd.{field_name} == {value}')
            
            # Min length filter
            if 'min_length' in filters:
                conditions.append(f"LENGTH(d.{field_name}) >= {filters['min_length']}")
            
            # Max length filter
            if 'max_length' in filters:
                conditions.append(f"LENGTH(d.{field_name}) <= {filters['max_length']}")
            
            # Contains filter
            if 'contains' in filters:
                value = filters['contains']
                conditions.append(f'CONTAINS(d.{field_name}, "{value}")')
            
            # Regex filter
            if 'regex' in filters:
                pattern = filters['regex']
                conditions.append(f'REGEX_TEST(d.{field_name}, "{pattern}")')
        
        return conditions
    
    def _update_statistics(self, pairs: List[Dict[str, Any]], execution_time: float):
        """
        Update internal statistics after candidate generation.
        
        Args:
            pairs: List of generated candidate pairs
            execution_time: Time taken to generate pairs (seconds)
        """
        self._stats.update({
            'total_pairs': len(pairs),
            'execution_time_seconds': round(execution_time, 2),
            'timestamp': datetime.now().isoformat()
        })
    
    def _normalize_pairs(
        self,
        pairs: List[Dict[str, Any]],
        key1_field: str = 'doc1_key',
        key2_field: str = 'doc2_key'
    ) -> List[Dict[str, Any]]:
        """
        Normalize candidate pairs to ensure doc1_key < doc2_key.
        
        This prevents duplicate pairs like (A, B) and (B, A).
        
        Args:
            pairs: List of candidate pairs
            key1_field: Field name for first document key
            key2_field: Field name for second document key
        
        Returns:
            Normalized pairs where doc1_key < doc2_key
        """
        normalized = []
        seen = set()
        
        for pair in pairs:
            key1 = pair.get(key1_field)
            key2 = pair.get(key2_field)
            
            if not key1 or not key2:
                continue
            
            # Ensure key1 < key2 for consistency
            if key1 > key2:
                key1, key2 = key2, key1
            
            # Skip duplicates
            pair_tuple = (key1, key2)
            if pair_tuple in seen:
                continue
            seen.add(pair_tuple)
            
            # Create normalized pair
            normalized_pair = pair.copy()
            normalized_pair[key1_field] = key1
            normalized_pair[key2_field] = key2
            normalized.append(normalized_pair)
        
        return normalized
    
    def __repr__(self) -> str:
        """String representation of the strategy."""
        return f"{self.__class__.__name__}(collection='{self.collection}')"

