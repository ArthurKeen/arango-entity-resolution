"""
Weighted multi-field similarity computation.

This module provides a reusable component for computing weighted similarity
scores across multiple fields between two documents. It supports multiple
similarity algorithms and configurable field weights.
"""

from typing import Dict, Any, Callable, Optional, Union
import logging

# Similarity algorithms
try:
    import jellyfish
    JELLYFISH_AVAILABLE = True
except ImportError:
    JELLYFISH_AVAILABLE = False

try:
    import Levenshtein
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False


class WeightedFieldSimilarity:
    """
    Compute weighted similarity across multiple fields.
    
    This class provides a reusable component for computing weighted similarity
    scores between two documents based on multiple fields. It supports:
    - Multiple similarity algorithms (Jaro-Winkler, Levenshtein, Jaccard)
    - Configurable field weights
    - Null value handling strategies
    - String normalization options
    
    Example:
        ```python
        similarity = WeightedFieldSimilarity(
            field_weights={'name': 0.4, 'address': 0.3, 'city': 0.3},
            algorithm='jaro_winkler',
            handle_nulls='skip'
        )
        
        doc1 = {'name': 'John Smith', 'address': '123 Main St', 'city': 'Boston'}
        doc2 = {'name': 'Jon Smith', 'address': '123 Main Street', 'city': 'Boston'}
        
        score = similarity.compute(doc1, doc2)
        # Returns: 0.92 (high similarity)
        ```
    """
    
    # Available similarity algorithms
    ALGORITHMS = {
        'jaro_winkler': 'jaro_winkler',
        'levenshtein': 'levenshtein',
        'jaccard': 'jaccard'
    }
    
    # Null handling strategies
    NULL_STRATEGIES = {'skip', 'zero', 'default'}
    
    def __init__(
        self,
        field_weights: Dict[str, float],
        algorithm: Union[str, Callable[[str, str], float]] = "jaro_winkler",
        normalize: bool = True,
        handle_nulls: str = "skip",
        normalization_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize weighted field similarity.
        
        Args:
            field_weights: Dictionary mapping field names to their weights.
                Example: {'name': 0.4, 'address': 0.3, 'city': 0.3}
                Weights will be normalized to sum to 1.0 if normalize=True.
            algorithm: Similarity algorithm to use:
                - "jaro_winkler" (default, best for names, requires jellyfish)
                - "levenshtein" (edit distance, requires python-Levenshtein)
                - "jaccard" (set-based similarity, built-in)
                - Custom callable: (str1, str2) -> float (0.0-1.0)
            normalize: Whether to normalize weights to sum to 1.0. Default True.
            handle_nulls: How to handle missing/null values:
                - "skip" (default): Skip null fields, don't count in weight
                - "zero": Count weight but contribute 0.0 to score
                - "default": Use default value (not yet implemented)
            normalization_config: String normalization options:
                {
                    "strip": True,              # Remove leading/trailing whitespace
                    "case": "upper",            # "upper", "lower", or None
                    "remove_punctuation": False,
                    "remove_extra_whitespace": True
                }
                Default: {"strip": True, "case": "upper", "remove_extra_whitespace": True}
        
        Raises:
            ValueError: If configuration is invalid
            ImportError: If required algorithm library not available
        """
        if not field_weights:
            raise ValueError("field_weights cannot be empty")
        
        if handle_nulls not in self.NULL_STRATEGIES:
            raise ValueError(
                f"handle_nulls must be one of {self.NULL_STRATEGIES}, "
                f"got: {handle_nulls}"
            )
        
        self.field_weights = field_weights
        self.normalize = normalize
        self.handle_nulls = handle_nulls
        
        # Normalize weights if requested
        if normalize:
            total = sum(field_weights.values())
            if total == 0:
                raise ValueError("Field weights cannot all be zero")
            self.field_weights = {
                k: v / total
                for k, v in field_weights.items()
            }
        
        # Set default normalization config
        default_norm = {
            "strip": True,
            "case": "upper",
            "remove_extra_whitespace": True,
            "remove_punctuation": False
        }
        self.normalization_config = {**default_norm, **(normalization_config or {})}
        
        # Set up similarity algorithm
        self.similarity_fn = self._setup_algorithm(algorithm)
        self.algorithm_name = algorithm if isinstance(algorithm, str) else "custom"
        
        # Initialize logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def compute(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any]
    ) -> float:
        """
        Compute weighted similarity between two documents.
        
        Args:
            doc1: First document dictionary
            doc2: Second document dictionary
        
        Returns:
            Weighted similarity score between 0.0 and 1.0
        
        Example:
            ```python
            doc1 = {'name': 'John Smith', 'address': '123 Main St'}
            doc2 = {'name': 'Jon Smith', 'address': '123 Main Street'}
            score = similarity.compute(doc1, doc2)
            # Returns: 0.87
            ```
        """
        total_score = 0.0
        total_weight = 0.0
        
        for field, weight in self.field_weights.items():
            val1 = doc1.get(field)
            val2 = doc2.get(field)
            
            # Handle nulls
            if val1 is None or val2 is None:
                if self.handle_nulls == "skip":
                    continue
                elif self.handle_nulls == "zero":
                    total_weight += weight
                    # Don't add to total_score (contributes 0.0)
                    continue
                # else: default value handling could go here in future
        
            # Normalize values
            val1_norm = self._normalize_value(str(val1) if val1 is not None else '')
            val2_norm = self._normalize_value(str(val2) if val2 is not None else '')
            
            if not val1_norm or not val2_norm:
                if self.handle_nulls == "skip":
                    continue
                elif self.handle_nulls == "zero":
                    total_weight += weight
                    continue
            
            # Compute field similarity
            try:
                score = self.similarity_fn(val1_norm, val2_norm)
                total_score += score * weight
                total_weight += weight
            except Exception as e:
                # Log but don't fail
                self.logger.warning(
                    f"Similarity computation failed for field '{field}': {e}",
                    exc_info=True
                )
                continue
        
        return round(total_score / total_weight, 4) if total_weight > 0 else 0.0
    
    def compute_detailed(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compute detailed per-field similarity scores.
        
        Args:
            doc1: First document dictionary
            doc2: Second document dictionary
        
        Returns:
            Dictionary with detailed scores:
            {
                "overall_score": 0.87,
                "field_scores": {
                    "name": 0.95,
                    "address": 0.82,
                    "city": 0.78
                },
                "weighted_score": 0.87
            }
        """
        field_scores = {}
        total_score = 0.0
        total_weight = 0.0
        
        for field, weight in self.field_weights.items():
            val1 = doc1.get(field)
            val2 = doc2.get(field)
            
            # Handle nulls
            if val1 is None or val2 is None:
                if self.handle_nulls == "skip":
                    field_scores[field] = None
                    continue
                elif self.handle_nulls == "zero":
                    field_scores[field] = 0.0
                    total_weight += weight
                    continue
            
            # Normalize values
            val1_norm = self._normalize_value(str(val1) if val1 is not None else '')
            val2_norm = self._normalize_value(str(val2) if val2 is not None else '')
            
            if not val1_norm or not val2_norm:
                if self.handle_nulls == "skip":
                    field_scores[field] = None
                    continue
                elif self.handle_nulls == "zero":
                    field_scores[field] = 0.0
                    total_weight += weight
                    continue
            
            # Compute field similarity
            try:
                score = self.similarity_fn(val1_norm, val2_norm)
                field_scores[field] = round(score, 4)
                total_score += score * weight
                total_weight += weight
            except Exception as e:
                self.logger.warning(
                    f"Similarity computation failed for field '{field}': {e}",
                    exc_info=True
                )
                field_scores[field] = 0.0
                total_weight += weight
        
        weighted_score = round(total_score / total_weight, 4) if total_weight > 0 else 0.0
        
        return {
            'overall_score': weighted_score,
            'field_scores': field_scores,
            'weighted_score': weighted_score
        }
    
    def _normalize_value(self, value: str) -> str:
        """
        Normalize a string value according to configuration.
        
        Args:
            value: Input string
        
        Returns:
            Normalized string
        """
        if self.normalization_config.get('strip'):
            value = value.strip()
        
        case = self.normalization_config.get('case')
        if case == 'upper':
            value = value.upper()
        elif case == 'lower':
            value = value.lower()
        
        if self.normalization_config.get('remove_extra_whitespace'):
            value = ' '.join(value.split())
        
        if self.normalization_config.get('remove_punctuation'):
            import string
            value = value.translate(str.maketrans('', '', string.punctuation))
        
        return value
    
    def _setup_algorithm(
        self,
        algorithm: Union[str, Callable[[str, str], float]]
    ) -> Callable[[str, str], float]:
        """
        Set up the similarity algorithm function.
        
        Args:
            algorithm: Algorithm name or callable
        
        Returns:
            Callable that computes similarity between two strings
        
        Raises:
            ValueError: If algorithm name is invalid
            ImportError: If required library not available
        """
        if callable(algorithm):
            return algorithm
        
        algorithm = algorithm.lower()
        
        if algorithm == "jaro_winkler":
            if not JELLYFISH_AVAILABLE:
                raise ImportError(
                    "jellyfish library required for jaro_winkler algorithm. "
                    "Install with: pip install jellyfish"
                )
            return jellyfish.jaro_winkler_similarity
        
        elif algorithm == "levenshtein":
            if not LEVENSHTEIN_AVAILABLE:
                raise ImportError(
                    "python-Levenshtein library required for levenshtein algorithm. "
                    "Install with: pip install python-Levenshtein"
                )
            # Normalize to 0-1 range
            return lambda s1, s2: 1.0 - (Levenshtein.distance(s1, s2) / max(len(s1), len(s2), 1))
        
        elif algorithm == "jaccard":
            return self._jaccard_similarity
        
        else:
            raise ValueError(
                f"Unknown algorithm: {algorithm}. "
                f"Supported: 'jaro_winkler', 'levenshtein', 'jaccard', or custom callable"
            )
    
    @staticmethod
    def _jaccard_similarity(str1: str, str2: str) -> float:
        """
        Compute Jaccard similarity between two strings (word-based).
        
        Args:
            str1: First string
            str2: Second string
        
        Returns:
            Jaccard similarity (0.0-1.0)
        """
        set1 = set(str1.split())
        set2 = set(str2.split())
        
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def __repr__(self) -> str:
        """String representation."""
        fields_str = ', '.join(self.field_weights.keys())
        return (f"WeightedFieldSimilarity("
                f"algorithm='{self.algorithm_name}', "
                f"fields=[{fields_str}], "
                f"handle_nulls='{self.handle_nulls}')")

