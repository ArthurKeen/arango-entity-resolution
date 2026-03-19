"""
Canonical MCP request contracts used by normalization helpers.

These contracts are internal and intentionally conservative: they model current
tool capabilities while leaving room for additive option blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MCPOptions:
    """Normalized option blocks shared across MCP tools."""

    blocking: Dict[str, Any] = field(default_factory=dict)
    similarity: Dict[str, Any] = field(default_factory=dict)
    clustering: Dict[str, Any] = field(default_factory=dict)
    active_learning: Dict[str, Any] = field(default_factory=dict)
    retrieval: Dict[str, Any] = field(default_factory=dict)
    gating: Dict[str, Any] = field(default_factory=dict)
    aliasing: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    passthrough: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FindDuplicatesRequest:
    """Canonical internal request shape for find_duplicates."""

    collection: str
    fields: List[str]
    strategy: str = "exact"
    confidence_threshold: float = 0.85
    max_block_size: int = 500
    store_clusters: bool = True
    edge_collection: Optional[str] = None
    enable_active_learning: bool = False
    feedback_collection: Optional[str] = None
    active_learning_refresh_every: int = 100
    active_learning_model: Optional[str] = None
    active_learning_low_threshold: float = 0.55
    active_learning_high_threshold: float = 0.80
    options: MCPOptions = field(default_factory=MCPOptions)
    deprecation_warnings: List[str] = field(default_factory=list)


@dataclass
class ResolveEntityRequest:
    """Canonical internal request shape for resolve_entity."""

    collection: str
    record: Dict[str, Any]
    fields: List[str]
    confidence_threshold: float = 0.80
    top_k: int = 10
    options: MCPOptions = field(default_factory=MCPOptions)
    deprecation_warnings: List[str] = field(default_factory=list)


@dataclass
class AdvisorRequestContext:
    """Common advisor request metadata normalized from legacy + options."""

    request_id: Optional[str] = None
    options: MCPOptions = field(default_factory=MCPOptions)
    deprecation_warnings: List[str] = field(default_factory=list)
