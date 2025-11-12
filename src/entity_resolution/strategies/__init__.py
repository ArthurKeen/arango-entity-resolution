"""
Blocking strategies for entity resolution.

This module provides various blocking strategies for generating candidate pairs
in entity resolution workflows. All strategies inherit from the base BlockingStrategy
class and provide configurable, reusable implementations.
"""

from .base_strategy import BlockingStrategy
from .collect_blocking import CollectBlockingStrategy
from .bm25_blocking import BM25BlockingStrategy

__all__ = [
    'BlockingStrategy',
    'CollectBlockingStrategy',
    'BM25BlockingStrategy',
]

