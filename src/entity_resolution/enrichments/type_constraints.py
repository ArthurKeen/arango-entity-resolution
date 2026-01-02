"""
Type Compatibility Filter

Enforces type compatibility constraints between source and target entities.
Prevents nonsensical matches by filtering candidates based on a user-defined
compatibility matrix.

Use Cases:
- Hardware: Signals only match Registers or Architecture Features
- Medical: Symptoms only match Conditions or Side Effects
- Legal: Clauses only match Obligations or Rights
- Organizations: Employees only match Positions or Roles
"""

from typing import List, Dict, Any, Set, Optional


class TypeCompatibilityFilter:
    """
    Filters entity resolution candidates based on type compatibility.
    
    This filter prevents semantic drift by ensuring that entities are only
    matched to candidates of compatible types. For example, in hardware design,
    a Signal should not match an Instruction entity, even if they have similar names.
    
    Attributes:
        compatibility_matrix (Dict[str, Set[str]]): Maps source types to sets of compatible target types
        strict_mode (bool): If True, reject candidates with unknown types
        unknown_type_label (str): Label used for entities with no type information
    
    Example:
        >>> filter = TypeCompatibilityFilter({
        ...     'signal': {'register', 'signal', 'architecture_feature'},
        ...     'module': {'processor_component', 'hardware_interface'},
        ...     'port': {'register', 'signal', 'hardware_interface'}
        ... })
        >>> 
        >>> # Filter candidates for a signal
        >>> valid_candidates = filter.filter_candidates(
        ...     source_type='signal',
        ...     candidates=[
        ...         {'name': 'ESR', 'type': 'register'},       # Valid
        ...         {'name': 'ADD', 'type': 'instruction'},    # Filtered out
        ...         {'name': 'CLK', 'type': 'signal'}          # Valid
        ...     ]
        ... )
        >>> len(valid_candidates)
        2
    """
    
    def __init__(
        self,
        compatibility_matrix: Dict[str, Set[str]],
        strict_mode: bool = False,
        unknown_type_label: str = 'UNKNOWN'
    ):
        """
        Initialize the Type Compatibility Filter.
        
        Args:
            compatibility_matrix: Maps source types to sets of compatible target types
                                 Example: {'signal': {'register', 'signal'}}
            strict_mode: If True, reject candidates with unknown/missing types
                        If False, allow unknown types (default behavior)
            unknown_type_label: Label to use for entities without type information
        
        Example:
            >>> # Hardware-specific compatibility
            >>> hw_matrix = {
            ...     'signal': {'register', 'signal', 'architecture_feature', 'UNKNOWN'},
            ...     'module': {'processor_component', 'memory_unit', 'UNKNOWN'},
            ...     'port': {'register', 'signal', 'hardware_interface', 'UNKNOWN'}
            ... }
            >>> filter = TypeCompatibilityFilter(hw_matrix)
        """
        self.compatibility_matrix = {
            k: set(v) if not isinstance(v, set) else v 
            for k, v in compatibility_matrix.items()
        }
        self.strict_mode = strict_mode
        self.unknown_type_label = unknown_type_label
    
    def is_compatible(self, source_type: str, target_type: str) -> bool:
        """
        Check if a source type is compatible with a target type.
        
        Args:
            source_type: Type of the source entity
            target_type: Type of the candidate entity
        
        Returns:
            True if types are compatible, False otherwise
        
        Example:
            >>> filter = TypeCompatibilityFilter({
            ...     'signal': {'register', 'signal'}
            ... })
            >>> filter.is_compatible('signal', 'register')
            True
            >>> filter.is_compatible('signal', 'instruction')
            False
        """
        # Handle missing types
        if not source_type:
            source_type = self.unknown_type_label
        if not target_type:
            target_type = self.unknown_type_label
        
        # In strict mode, reject unknown types
        if self.strict_mode:
            if source_type == self.unknown_type_label or target_type == self.unknown_type_label:
                return False
        
        # If source type not in matrix, allow all (permissive)
        if source_type not in self.compatibility_matrix:
            return not self.strict_mode
        
        # Check compatibility
        compatible_types = self.compatibility_matrix[source_type]
        return target_type in compatible_types
    
    def filter_candidates(
        self,
        source_type: str,
        candidates: List[Dict[str, Any]],
        type_field: str = 'type'
    ) -> List[Dict[str, Any]]:
        """
        Filter a list of candidates to only compatible types.
        
        Args:
            source_type: Type of the source entity being resolved
            candidates: List of candidate entities
            type_field: Name of field containing type information (default: 'type')
        
        Returns:
            Filtered list of candidates with compatible types
        
        Example:
            >>> candidates = [
            ...     {'name': 'ESR', 'type': 'register', 'score': 0.9},
            ...     {'name': 'ADD', 'type': 'instruction', 'score': 0.85},
            ...     {'name': 'CLK', 'type': 'signal', 'score': 0.8}
            ... ]
            >>> filtered = filter.filter_candidates('signal', candidates)
            >>> [c['name'] for c in filtered]
            ['ESR', 'CLK']
        """
        return [
            cand for cand in candidates
            if self.is_compatible(source_type, cand.get(type_field, self.unknown_type_label))
        ]
    
    def filter_candidates_batch(
        self,
        items: List[Dict[str, Any]],
        candidates_per_item: Dict[str, List[Dict[str, Any]]],
        source_type_field: str = 'type',
        target_type_field: str = 'type'
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Filter candidates for multiple items at once.
        
        Args:
            items: List of source items to resolve
            candidates_per_item: Dict mapping item IDs to their candidate lists
            source_type_field: Field name for source type
            target_type_field: Field name for target type
        
        Returns:
            Dict mapping item IDs to filtered candidate lists
        
        Example:
            >>> items = [
            ...     {'id': 'sig1', 'type': 'signal'},
            ...     {'id': 'mod1', 'type': 'module'}
            ... ]
            >>> candidates = {
            ...     'sig1': [{'type': 'register'}, {'type': 'instruction'}],
            ...     'mod1': [{'type': 'processor_component'}, {'type': 'signal'}]
            ... }
            >>> filtered = filter.filter_candidates_batch(items, candidates)
        """
        result = {}
        
        for item in items:
            item_id = item.get('id', item.get('_id'))
            source_type = item.get(source_type_field, self.unknown_type_label)
            
            if item_id in candidates_per_item:
                result[item_id] = self.filter_candidates(
                    source_type,
                    candidates_per_item[item_id],
                    type_field=target_type_field
                )
        
        return result
    
    def get_compatible_types(self, source_type: str) -> Set[str]:
        """
        Get the set of compatible types for a source type.
        
        Args:
            source_type: Source entity type
        
        Returns:
            Set of compatible target types
        
        Example:
            >>> filter = TypeCompatibilityFilter({
            ...     'signal': {'register', 'signal', 'architecture_feature'}
            ... })
            >>> compatible = filter.get_compatible_types('signal')
            >>> 'register' in compatible
            True
        """
        if source_type not in self.compatibility_matrix:
            if self.strict_mode:
                return set()
            else:
                # In permissive mode, return all known types
                all_types = set()
                for types in self.compatibility_matrix.values():
                    all_types.update(types)
                return all_types
        
        return self.compatibility_matrix[source_type].copy()
    
    def add_compatibility(self, source_type: str, target_types: Set[str]):
        """
        Add or update compatibility rules for a source type.
        
        Args:
            source_type: Source entity type
            target_types: Set of compatible target types
        
        Example:
            >>> filter = TypeCompatibilityFilter({})
            >>> filter.add_compatibility('signal', {'register', 'signal'})
            >>> filter.is_compatible('signal', 'register')
            True
        """
        self.compatibility_matrix[source_type] = set(target_types)
    
    def get_statistics(self, items: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
                      source_type_field: str = 'type', target_type_field: str = 'type') -> Dict[str, Any]:
        """
        Get filtering statistics for analysis.
        
        Args:
            items: Source items
            candidates: All candidates before filtering
            source_type_field: Field name for source type
            target_type_field: Field name for target type
        
        Returns:
            Statistics dict with counts and percentages
        
        Example:
            >>> stats = filter.get_statistics(source_items, all_candidates)
            >>> print(f"Filtered out {stats['filtered_percentage']:.1f}%")
        """
        total_candidates = len(candidates)
        
        # Count compatible candidates
        compatible_count = 0
        type_distribution = {}
        
        for item in items:
            source_type = item.get(source_type_field, self.unknown_type_label)
            
            for cand in candidates:
                target_type = cand.get(target_type_field, self.unknown_type_label)
                
                if self.is_compatible(source_type, target_type):
                    compatible_count += 1
                
                # Track type distribution
                if target_type not in type_distribution:
                    type_distribution[target_type] = 0
                type_distribution[target_type] += 1
        
        filtered_count = total_candidates - compatible_count
        
        return {
            'total_candidates': total_candidates,
            'compatible_candidates': compatible_count,
            'filtered_candidates': filtered_count,
            'filtered_percentage': (filtered_count / total_candidates * 100) if total_candidates > 0 else 0,
            'type_distribution': type_distribution
        }

