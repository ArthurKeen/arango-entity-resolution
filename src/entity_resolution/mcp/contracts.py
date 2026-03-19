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
    execution: Dict[str, Any] = field(default_factory=dict)
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
    min_margin: float = 0.0
    require_token_overlap: bool = False
    token_overlap_bypass_score: float = 1.0
    word_index_stopwords: List[str] = field(default_factory=list)
    token_type_affinity: Dict[str, List[str]] = field(default_factory=dict)
    target_type_field: str = "type"
    stages: List[Dict[str, Any]] = field(default_factory=list)
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
class CrossCollectionRequest:
    """Canonical internal request shape for resolve_entity_cross_collection."""

    source_collection: str
    target_collection: str
    source_fields: Dict[str, str]
    target_fields: Dict[str, str]
    field_weights: Dict[str, float] = field(default_factory=dict)
    blocking_fields: List[str] = field(default_factory=list)
    blocking_strategy: str = "exact"
    confidence_threshold: float = 0.85
    edge_collection: Optional[str] = None
    search_view: Optional[str] = None
    use_bm25: bool = True
    bm25_weight: float = 0.2
    candidate_limit: int = 1000
    batch_size: int = 100
    max_runtime_ms: int = 300000
    deterministic_tiebreak: bool = True
    return_diagnostics: bool = True
    target_filter: Optional[Dict[str, Any]] = None
    source_skip_values: Optional[Dict[str, Any]] = None
    options: MCPOptions = field(default_factory=MCPOptions)
    deprecation_warnings: List[str] = field(default_factory=list)


@dataclass
class AdvisorRequestContext:
    """Common advisor request metadata normalized from legacy + options."""

    request_id: Optional[str] = None
    options: MCPOptions = field(default_factory=MCPOptions)
    deprecation_warnings: List[str] = field(default_factory=list)
