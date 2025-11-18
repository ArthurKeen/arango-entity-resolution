"""
Similarity computation components for entity resolution.

This module provides reusable similarity computation classes that can be used
independently or as part of larger ER pipelines.
"""

from .weighted_field_similarity import WeightedFieldSimilarity

__all__ = [
    'WeightedFieldSimilarity',
]

