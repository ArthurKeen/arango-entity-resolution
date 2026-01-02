"""
Entity Resolution Enrichments for Arango Entity Resolution Library

This package provides enhancements for entity resolution in technical
and hierarchical domains.

Components:
- HierarchicalContextResolver: Uses parent context to improve child resolution
- TypeCompatibilityFilter: Enforces type compatibility constraints  
- AcronymExpansionHandler: Handles acronym expansion in searches
- RelationshipProvenanceSweeper: Remaps relationships through consolidation

Example:
    >>> from ic_enrichment import HierarchicalContextResolver
    >>> resolver = HierarchicalContextResolver(weight=0.3)
    >>> matches = resolver.resolve_with_context(item, candidates, parent_context)
"""

__version__ = '0.1.0'
__author__ = 'Arthur Keen'
__license__ = 'MIT'

from .context_resolver import HierarchicalContextResolver
from .type_constraints import TypeCompatibilityFilter
from .acronym_handler import AcronymExpansionHandler
from .relationship_sweeper import RelationshipProvenanceSweeper

__all__ = [
    'HierarchicalContextResolver',
    'TypeCompatibilityFilter',
    'AcronymExpansionHandler',
    'RelationshipProvenanceSweeper',
]

