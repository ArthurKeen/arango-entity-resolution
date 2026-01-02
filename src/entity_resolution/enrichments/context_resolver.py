"""
Hierarchical Context Resolver

Uses parent entity context to improve child entity resolution accuracy.
Particularly useful for hierarchical data structures where child entities
should be semantically related to their parents.

Use Cases:
- Hardware: Module → Port/Signal hierarchy
- Organizations: Department → Employee hierarchy  
- Products: Category → SKU hierarchy
- File Systems: Directory → File hierarchy
"""

import re
from typing import List, Dict, Any, Optional


class HierarchicalContextResolver:
    """
    Resolves entities using hierarchical context from parent entities.
    
    This resolver improves match quality by considering the semantic context
    of a parent entity when resolving its children. For example, when resolving
    a hardware signal, the module's description can help disambiguate between
    similar signal names in different contexts.
    
    Attributes:
        parent_field (str): Field name containing parent identifier
        context_field (str): Field name containing parent context (e.g., 'description', 'summary')
        context_weight (float): Weight for context score (0.0-1.0), blended with base similarity
        stop_words (set): Common words to exclude from context overlap calculation
    
    Example:
        >>> resolver = HierarchicalContextResolver(
        ...     parent_field='module_name',
        ...     context_field='summary',
        ...     context_weight=0.3
        ... )
        >>> 
        >>> # Get parent context
        >>> parent_context = module_summaries[signal['module_name']]
        >>> 
        >>> # Resolve with context
        >>> matches = resolver.resolve_with_context(
        ...     item=signal,
        ...     candidates=entity_candidates,
        ...     parent_context=parent_context,
        ...     base_similarity_fn=lambda c: compute_similarity(signal, c)
        ... )
    """
    
    def __init__(
        self,
        parent_field: str = 'parent_id',
        context_field: str = 'description',
        context_weight: float = 0.3,
        base_weight: float = 0.7,
        stop_words: Optional[set] = None
    ):
        """
        Initialize the Hierarchical Context Resolver.
        
        Args:
            parent_field: Name of field containing parent identifier
            context_field: Name of field in candidates containing context to match against
            context_weight: Weight for context overlap score (0.0-1.0)
            base_weight: Weight for base similarity score (should sum to 1.0 with context_weight)
            stop_words: Set of words to exclude from context analysis (uses defaults if None)
        
        Raises:
            ValueError: If weights don't sum to 1.0 or are out of range
        """
        if not (0.0 <= context_weight <= 1.0):
            raise ValueError(f"context_weight must be between 0.0 and 1.0, got {context_weight}")
        
        if not (0.0 <= base_weight <= 1.0):
            raise ValueError(f"base_weight must be between 0.0 and 1.0, got {base_weight}")
        
        if abs((context_weight + base_weight) - 1.0) > 0.01:
            raise ValueError(
                f"context_weight ({context_weight}) and base_weight ({base_weight}) "
                f"must sum to 1.0, got {context_weight + base_weight}"
            )
        
        self.parent_field = parent_field
        self.context_field = context_field
        self.context_weight = context_weight
        self.base_weight = base_weight
        
        # Default stop words (common English words with little semantic value)
        self.stop_words = stop_words or {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'of', 'in', 'to', 'for', 'and', 'or', 'but', 'with', 'on', 'at', 'by',
            'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their'
        }
    
    def calculate_token_overlap(self, text1: str, text2: str) -> float:
        """
        Calculate semantic overlap between two text strings.
        
        Uses token-based overlap coefficient after removing stop words.
        
        Args:
            text1: First text string
            text2: Second text string
        
        Returns:
            Overlap coefficient (0.0-1.0), where 1.0 means perfect overlap
        
        Example:
            >>> resolver = HierarchicalContextResolver()
            >>> overlap = resolver.calculate_token_overlap(
            ...     "exception status register",
            ...     "register stores exception status"
            ... )
            >>> print(f"{overlap:.2f}")  # High overlap
            0.75
        """
        if not text1 or not text2:
            return 0.0
        
        # Tokenize (extract words)
        tokens1 = set(re.findall(r'\w+', text1.lower()))
        tokens2 = set(re.findall(r'\w+', text2.lower()))
        
        # Remove stop words
        tokens1 -= self.stop_words
        tokens2 -= self.stop_words
        
        if not tokens1 or not tokens2:
            return 0.0
        
        # Calculate overlap coefficient (intersection / min set size)
        intersection = tokens1.intersection(tokens2)
        min_len = min(len(tokens1), len(tokens2))
        
        return len(intersection) / min_len if min_len > 0 else 0.0
    
    def resolve_with_context(
        self,
        item: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        parent_context: str,
        base_similarity_fn: callable,
        threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Resolve an item to candidates using parent context to boost scores.
        
        Args:
            item: Item to resolve (must have fields for matching)
            candidates: List of candidate entities to match against
            parent_context: Context string from parent entity (e.g., module summary)
            base_similarity_fn: Function to compute base similarity, signature: fn(candidate) -> float
            threshold: Minimum final score to include in results (default: 0.0)
        
        Returns:
            List of candidates with boosted scores, sorted by final_score descending.
            Each candidate dict will have added fields:
            - 'base_score': Original similarity score
            - 'context_score': Context overlap score
            - 'final_score': Weighted combination of base and context
        
        Example:
            >>> def similarity(candidate):
            ...     # Your similarity logic here
            ...     return 0.8
            >>> 
            >>> matches = resolver.resolve_with_context(
            ...     item={'name': 'esr', 'parent': 'or1200_except'},
            ...     candidates=[
            ...         {'name': 'ESR Register', 'description': 'exception status'},
            ...         {'name': 'ESR Signal', 'description': 'error signal register'}
            ...     ],
            ...     parent_context='exception handling module',
            ...     base_similarity_fn=similarity
            ... )
        """
        if not parent_context:
            # No context available, just use base similarity
            results = []
            for cand in candidates:
                base_score = base_similarity_fn(cand)
                if base_score >= threshold:
                    cand_copy = cand.copy()
                    cand_copy['base_score'] = base_score
                    cand_copy['context_score'] = 0.0
                    cand_copy['final_score'] = base_score
                    results.append(cand_copy)
            results.sort(key=lambda x: x['final_score'], reverse=True)
            return results
        
        results = []
        for cand in candidates:
            # Compute base similarity
            base_score = base_similarity_fn(cand)
            
            # Get candidate's context field
            cand_context = cand.get(self.context_field, '')
            
            # Compute context overlap
            context_score = self.calculate_token_overlap(parent_context, cand_context)
            
            # Blend scores
            if context_score > 0.0:
                # Meaningful context overlap - blend scores
                final_score = (base_score * self.base_weight) + (context_score * self.context_weight)
            else:
                # No context overlap - apply small penalty
                final_score = base_score * 0.9
            
            if final_score >= threshold:
                cand_copy = cand.copy()
                cand_copy['base_score'] = base_score
                cand_copy['context_score'] = context_score
                cand_copy['final_score'] = final_score
                results.append(cand_copy)
        
        # Sort by final score descending
        results.sort(key=lambda x: x['final_score'], reverse=True)
        
        return results
    
    def get_parent_context(
        self,
        item: Dict[str, Any],
        parent_contexts: Dict[str, str]
    ) -> Optional[str]:
        """
        Helper method to extract parent context for an item.
        
        Args:
            item: Item containing parent identifier in parent_field
            parent_contexts: Dictionary mapping parent IDs to their context strings
        
        Returns:
            Parent context string, or None if not found
        
        Example:
            >>> contexts = {'module_a': 'handles exceptions', 'module_b': 'memory management'}
            >>> item = {'name': 'signal_x', 'parent_id': 'module_a'}
            >>> context = resolver.get_parent_context(item, contexts)
            >>> print(context)
            'handles exceptions'
        """
        parent_id = item.get(self.parent_field)
        if parent_id:
            return parent_contexts.get(parent_id)
        return None

