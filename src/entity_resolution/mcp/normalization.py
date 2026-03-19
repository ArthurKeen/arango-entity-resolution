"""
Normalization helpers for MCP tool arguments.

The goal is backward compatibility: current top-level args still work while new
`options` blocks become the canonical internal shape.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .contracts import AdvisorRequestContext, FindDuplicatesRequest, MCPOptions, ResolveEntityRequest


def normalize_find_duplicates_args(
    *,
    collection: str,
    fields: List[str],
    strategy: str = "exact",
    confidence_threshold: float = 0.85,
    max_block_size: int = 500,
    store_clusters: bool = True,
    edge_collection: Optional[str] = None,
    enable_active_learning: bool = False,
    feedback_collection: Optional[str] = None,
    active_learning_refresh_every: int = 100,
    active_learning_model: Optional[str] = None,
    active_learning_low_threshold: float = 0.55,
    active_learning_high_threshold: float = 0.80,
    options: Optional[Dict[str, Any]] = None,
) -> FindDuplicatesRequest:
    """Normalize find_duplicates args into a canonical request contract."""
    normalized_options = _normalize_options(options)
    warnings: List[str] = []

    strategy = _select_value(
        key="options.blocking.strategy",
        legacy_key="strategy",
        legacy_value=strategy,
        option_value=_nested_get(normalized_options, "blocking", "strategy"),
        warnings=warnings,
    )
    fields = _select_value(
        key="options.blocking.fields",
        legacy_key="fields",
        legacy_value=fields,
        option_value=_nested_get(normalized_options, "blocking", "fields"),
        warnings=warnings,
    )
    max_block_size = int(
        _select_value(
            key="options.blocking.max_block_size",
            legacy_key="max_block_size",
            legacy_value=max_block_size,
            option_value=_nested_get(normalized_options, "blocking", "max_block_size"),
            warnings=warnings,
        )
    )
    confidence_threshold = float(
        _select_value(
            key="options.similarity.confidence_threshold",
            legacy_key="confidence_threshold",
            legacy_value=confidence_threshold,
            option_value=_nested_get(normalized_options, "similarity", "confidence_threshold"),
            warnings=warnings,
        )
    )
    store_clusters = bool(
        _select_value(
            key="options.clustering.store_clusters",
            legacy_key="store_clusters",
            legacy_value=store_clusters,
            option_value=_nested_get(normalized_options, "clustering", "store_clusters"),
            warnings=warnings,
        )
    )
    edge_collection = _select_value(
        key="options.clustering.edge_collection",
        legacy_key="edge_collection",
        legacy_value=edge_collection,
        option_value=_nested_get(normalized_options, "clustering", "edge_collection"),
        warnings=warnings,
    )
    enable_active_learning = bool(
        _select_value(
            key="options.active_learning.enabled",
            legacy_key="enable_active_learning",
            legacy_value=enable_active_learning,
            option_value=_nested_get(normalized_options, "active_learning", "enabled"),
            warnings=warnings,
        )
    )
    feedback_collection = _select_value(
        key="options.active_learning.feedback_collection",
        legacy_key="feedback_collection",
        legacy_value=feedback_collection,
        option_value=_nested_get(normalized_options, "active_learning", "feedback_collection"),
        warnings=warnings,
    )
    active_learning_refresh_every = int(
        _select_value(
            key="options.active_learning.refresh_every",
            legacy_key="active_learning_refresh_every",
            legacy_value=active_learning_refresh_every,
            option_value=_nested_get(normalized_options, "active_learning", "refresh_every"),
            warnings=warnings,
        )
    )
    active_learning_model = _select_value(
        key="options.active_learning.model",
        legacy_key="active_learning_model",
        legacy_value=active_learning_model,
        option_value=_nested_get(normalized_options, "active_learning", "model"),
        warnings=warnings,
    )
    active_learning_low_threshold = float(
        _select_value(
            key="options.active_learning.low_threshold",
            legacy_key="active_learning_low_threshold",
            legacy_value=active_learning_low_threshold,
            option_value=_nested_get(normalized_options, "active_learning", "low_threshold"),
            warnings=warnings,
        )
    )
    active_learning_high_threshold = float(
        _select_value(
            key="options.active_learning.high_threshold",
            legacy_key="active_learning_high_threshold",
            legacy_value=active_learning_high_threshold,
            option_value=_nested_get(normalized_options, "active_learning", "high_threshold"),
            warnings=warnings,
        )
    )

    return FindDuplicatesRequest(
        collection=collection,
        fields=[str(f) for f in (fields or [])],
        strategy=str(strategy),
        confidence_threshold=confidence_threshold,
        max_block_size=max(1, max_block_size),
        store_clusters=store_clusters,
        edge_collection=edge_collection,
        enable_active_learning=enable_active_learning,
        feedback_collection=feedback_collection,
        active_learning_refresh_every=max(1, active_learning_refresh_every),
        active_learning_model=active_learning_model,
        active_learning_low_threshold=active_learning_low_threshold,
        active_learning_high_threshold=active_learning_high_threshold,
        options=MCPOptions(**normalized_options),
        deprecation_warnings=warnings,
    )


def normalize_resolve_entity_args(
    *,
    collection: str,
    record: Dict[str, Any],
    fields: List[str],
    confidence_threshold: float = 0.80,
    top_k: int = 10,
    options: Optional[Dict[str, Any]] = None,
) -> ResolveEntityRequest:
    """Normalize resolve_entity args into a canonical request contract."""
    normalized_options = _normalize_options(options)
    warnings: List[str] = []

    fields = _select_value(
        key="options.retrieval.fields",
        legacy_key="fields",
        legacy_value=fields,
        option_value=_nested_get(normalized_options, "retrieval", "fields"),
        warnings=warnings,
    )
    confidence_threshold = float(
        _select_value(
            key="options.similarity.confidence_threshold",
            legacy_key="confidence_threshold",
            legacy_value=confidence_threshold,
            option_value=_nested_get(normalized_options, "similarity", "confidence_threshold"),
            warnings=warnings,
        )
    )
    top_k = int(
        _select_value(
            key="options.retrieval.top_k",
            legacy_key="top_k",
            legacy_value=top_k,
            option_value=_nested_get(normalized_options, "retrieval", "top_k"),
            warnings=warnings,
        )
    )

    return ResolveEntityRequest(
        collection=collection,
        record=record or {},
        fields=[str(f) for f in (fields or [])],
        confidence_threshold=confidence_threshold,
        top_k=max(1, top_k),
        options=MCPOptions(**normalized_options),
        deprecation_warnings=warnings,
    )


def normalize_advisor_context(
    *,
    request_id: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> AdvisorRequestContext:
    """Normalize advisor request metadata/options."""
    normalized_options = _normalize_options(options)
    return AdvisorRequestContext(
        request_id=request_id,
        options=MCPOptions(**normalized_options),
        deprecation_warnings=[],
    )


def _normalize_options(options: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ValueError("options must be an object/dict when provided")

    known_blocks = {
        "blocking",
        "similarity",
        "clustering",
        "active_learning",
        "retrieval",
        "gating",
        "aliasing",
        "diagnostics",
    }
    normalized: Dict[str, Dict[str, Any]] = {}
    for block in known_blocks:
        value = options.get(block, {})
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ValueError(f"options.{block} must be an object/dict")
        normalized[block] = value

    passthrough = {k: v for k, v in options.items() if k not in known_blocks}
    normalized["passthrough"] = passthrough
    return normalized


def _nested_get(options: Dict[str, Dict[str, Any]], block: str, key: str) -> Any:
    return options.get(block, {}).get(key)


def _select_value(
    *,
    key: str,
    legacy_key: str,
    legacy_value: Any,
    option_value: Any,
    warnings: List[str],
) -> Any:
    if option_value is None:
        return legacy_value
    if legacy_value != option_value:
        warnings.append(
            f"Both legacy field '{legacy_key}' and '{key}' were provided; using '{key}'."
        )
    return option_value
