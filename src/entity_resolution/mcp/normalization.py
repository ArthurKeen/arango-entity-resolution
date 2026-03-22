"""
Normalization helpers for MCP tool arguments.

The goal is backward compatibility: current top-level args still work while new
`options` blocks become the canonical internal shape.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    AdvisorRequestContext,
    CrossCollectionRequest,
    FindDuplicatesRequest,
    MCPOptions,
    ResolveEntityRequest,
)


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
    similarity_type = str(_nested_get(normalized_options, "similarity", "type") or "default").strip().lower()
    token_jaccard_fields_raw = _nested_get(normalized_options, "similarity", "token_jaccard_fields") or []
    if token_jaccard_fields_raw and not isinstance(token_jaccard_fields_raw, list):
        raise ValueError("options.similarity.token_jaccard_fields must be an array/list when provided")
    token_jaccard_fields = [str(f).strip() for f in token_jaccard_fields_raw if str(f).strip()]
    token_jaccard_min_score = float(_nested_get(normalized_options, "similarity", "token_jaccard_min_score") or 0.0)
    gating_mode = str(_nested_get(normalized_options, "gating", "mode") or "enforce").strip().lower()
    if gating_mode not in {"enforce", "report_only", "shadow"}:
        raise ValueError("options.gating.mode must be one of: enforce, report_only, shadow")
    min_margin = float(_nested_get(normalized_options, "gating", "min_margin") or 0.0)
    require_token_overlap = bool(_nested_get(normalized_options, "gating", "require_token_overlap") or False)
    token_overlap_bypass_score = float(
        _nested_get(normalized_options, "gating", "token_overlap_bypass_score") or 1.0
    )
    stopwords_raw = _nested_get(normalized_options, "gating", "word_index_stopwords") or []
    if not isinstance(stopwords_raw, list):
        raise ValueError("options.gating.word_index_stopwords must be an array/list when provided")
    word_index_stopwords = [str(s).lower() for s in stopwords_raw]
    token_type_affinity = _normalize_token_type_affinity(
        _nested_get(normalized_options, "gating", "token_type_affinity")
    )
    target_type_field = str(_nested_get(normalized_options, "gating", "target_type_field") or "type")
    alias_sources = _normalize_aliasing_sources(_nested_get(normalized_options, "aliasing", "sources"))
    stages = _normalize_stages(_nested_get(normalized_options, "passthrough", "stages"))

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
        similarity_type=similarity_type,
        token_jaccard_fields=token_jaccard_fields,
        token_jaccard_min_score=max(0.0, min(1.0, token_jaccard_min_score)),
        gating_mode=gating_mode,
        min_margin=max(0.0, min_margin),
        require_token_overlap=require_token_overlap,
        token_overlap_bypass_score=max(0.0, min(1.0, token_overlap_bypass_score)),
        word_index_stopwords=word_index_stopwords,
        token_type_affinity=token_type_affinity,
        target_type_field=target_type_field,
        alias_sources=alias_sources,
        stages=stages,
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


def normalize_cross_collection_args(
    *,
    source_collection: str,
    target_collection: str,
    source_fields: List[str],
    target_fields: List[str],
    options: Optional[Dict[str, Any]] = None,
) -> CrossCollectionRequest:
    """Normalize resolve_entity_cross_collection args into a canonical request."""
    normalized_options = _normalize_options(options)
    warnings: List[str] = []

    # --- field mapping ---
    retrieval = normalized_options.get("retrieval", {})
    field_mapping = retrieval.get("field_mapping")
    source_map: Dict[str, str] = {}
    target_map: Dict[str, str] = {}

    if field_mapping is not None:
        if not isinstance(field_mapping, dict):
            raise ValueError("options.retrieval.field_mapping must be an object/dict")
        for logical_field, pair in field_mapping.items():
            if not isinstance(pair, dict):
                raise ValueError(
                    "options.retrieval.field_mapping values must be objects with source/target keys"
                )
            src = str(pair.get("source", "")).strip()
            tgt = str(pair.get("target", "")).strip()
            if not src or not tgt:
                raise ValueError(
                    "options.retrieval.field_mapping entries must include non-empty source and target"
                )
            source_map[str(logical_field)] = src
            target_map[str(logical_field)] = tgt
        if source_fields or target_fields:
            warnings.append(
                "Both legacy fields 'source_fields'/'target_fields' and "
                "'options.retrieval.field_mapping' were provided; using field_mapping."
            )
    else:
        if len(source_fields) != len(target_fields):
            raise ValueError(
                "source_fields and target_fields must have the same length "
                "unless options.retrieval.field_mapping is provided"
            )
        for sf, tf in zip(source_fields, target_fields):
            logical = str(sf)
            source_map[logical] = str(sf)
            target_map[logical] = str(tf)

    if not source_map:
        raise ValueError("At least one field mapping is required for cross-collection resolution")

    # --- similarity ---
    similarity = normalized_options.get("similarity", {})
    raw_weights = similarity.get("field_weights")
    if raw_weights is not None:
        if not isinstance(raw_weights, dict):
            raise ValueError("options.similarity.field_weights must be an object/dict")
        field_weights = {str(k): float(v) for k, v in raw_weights.items()}
    else:
        eq = 1.0 / float(len(source_map))
        field_weights = {logical: eq for logical in source_map}

    confidence_threshold = float(similarity.get("confidence_threshold", 0.85))

    # --- blocking ---
    blocking = normalized_options.get("blocking", {})
    blocking_fields_opt = blocking.get("fields")
    if blocking_fields_opt is not None:
        if not isinstance(blocking_fields_opt, list):
            raise ValueError("options.blocking.fields must be an array/list when provided")
        blocking_fields = [str(f) for f in blocking_fields_opt]
    else:
        blocking_fields = [next(iter(source_map.keys()))]

    blocking_strategy = str(blocking.get("strategy", "exact"))
    search_view = blocking.get("search_view")
    use_bm25 = bool(blocking.get("use_bm25", True))
    bm25_weight = float(blocking.get("bm25_weight", 0.2))

    # --- execution ---
    execution = normalized_options.get("execution", {})
    batch_size = max(1, int(execution.get("batch_size", 100)))
    max_runtime_ms = max(1, int(execution.get("max_runtime_ms", 300000)))
    candidate_limit = max(
        1,
        int(retrieval.get("candidate_limit", execution.get("candidate_limit", 1000))),
    )
    deterministic_tiebreak = bool(retrieval.get("deterministic_tiebreak", True))

    # --- clustering ---
    clustering = normalized_options.get("clustering", {})
    edge_collection = clustering.get("edge_collection")
    if edge_collection is None:
        edge_collection = f"{source_collection}_{target_collection}_resolved_edges"
    edge_collection = str(edge_collection)

    # --- filters ---
    target_filter = retrieval.get("target_filter")
    if target_filter is not None and not isinstance(target_filter, dict):
        raise ValueError("options.retrieval.target_filter must be an object/dict")
    source_skip_values = retrieval.get("source_skip_values")
    if source_skip_values is not None and not isinstance(source_skip_values, dict):
        raise ValueError("options.retrieval.source_skip_values must be an object/dict")

    # --- diagnostics ---
    diagnostics = normalized_options.get("diagnostics", {})
    return_diagnostics = bool(diagnostics.get("return_diagnostics", True))

    return CrossCollectionRequest(
        source_collection=source_collection,
        target_collection=target_collection,
        source_fields=source_map,
        target_fields=target_map,
        field_weights=field_weights,
        blocking_fields=blocking_fields,
        blocking_strategy=blocking_strategy,
        confidence_threshold=confidence_threshold,
        edge_collection=edge_collection,
        search_view=search_view,
        use_bm25=use_bm25,
        bm25_weight=bm25_weight,
        candidate_limit=candidate_limit,
        batch_size=batch_size,
        max_runtime_ms=max_runtime_ms,
        deterministic_tiebreak=deterministic_tiebreak,
        return_diagnostics=return_diagnostics,
        target_filter=target_filter,
        source_skip_values=source_skip_values,
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
        "execution",
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


def _normalize_stages(value: Any) -> List[Dict[str, Any]]:
    """
    Normalize options.stages into a canonical list.

    C2 scaffold: validates schema minimally so handlers can consume a stable shape.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("options.stages must be an array/list when provided")

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"options.stages[{idx}] must be an object/dict")
        stage_type = str(item.get("type", "")).strip()
        if not stage_type:
            raise ValueError(f"options.stages[{idx}].type is required")
        stage: Dict[str, Any] = {"type": stage_type}
        if "fields" in item:
            if not isinstance(item["fields"], list):
                raise ValueError(f"options.stages[{idx}].fields must be an array/list")
            stage["fields"] = [str(f) for f in item["fields"]]
        if "min_score" in item:
            stage["min_score"] = float(item["min_score"])
        if "config" in item and isinstance(item["config"], dict):
            # Preserve stage-local extension knobs for future phases.
            stage["config"] = dict(item["config"])
        normalized.append(stage)
    return normalized


def _normalize_token_type_affinity(value: Any) -> Dict[str, List[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("options.gating.token_type_affinity must be an object/dict when provided")

    normalized: Dict[str, List[str]] = {}
    for token, raw in value.items():
        token_key = str(token).strip().lower()
        if not token_key:
            continue
        if isinstance(raw, list):
            allowed = [str(v).strip() for v in raw if str(v).strip()]
        elif isinstance(raw, dict):
            vals = raw.get("allowed_types", [])
            if not isinstance(vals, list):
                raise ValueError(
                    "options.gating.token_type_affinity.<token>.allowed_types must be an array/list"
                )
            allowed = [str(v).strip() for v in vals if str(v).strip()]
        else:
            raise ValueError(
                "options.gating.token_type_affinity values must be lists or objects with allowed_types"
            )
        if allowed:
            normalized[token_key] = allowed
    return normalized


def _normalize_aliasing_sources(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("options.aliasing.sources must be an array/list when provided")

    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"options.aliasing.sources[{idx}] must be an object/dict")
        source_type = str(item.get("type", "")).strip().lower()
        if not source_type:
            raise ValueError(f"options.aliasing.sources[{idx}].type is required")

        if source_type == "inline":
            raw_map = item.get("map", {})
            if not isinstance(raw_map, dict):
                raise ValueError(f"options.aliasing.sources[{idx}].map must be an object/dict")
            norm_map: Dict[str, List[str]] = {}
            for key, raw_vals in raw_map.items():
                token = str(key).strip().lower()
                if not token:
                    continue
                if isinstance(raw_vals, list):
                    vals = [str(v).strip().lower() for v in raw_vals if str(v).strip()]
                else:
                    vals = [str(raw_vals).strip().lower()] if str(raw_vals).strip() else []
                if vals:
                    norm_map[token] = vals
            out.append({"type": "inline", "map": norm_map})
            continue

        if source_type == "field":
            field = str(item.get("field", "")).strip()
            if not field:
                raise ValueError(f"options.aliasing.sources[{idx}].field is required for type=field")
            out.append({"type": "field", "field": field})
            continue

        if source_type == "acronym":
            out.append(
                {
                    "type": "acronym",
                    "auto": bool(item.get("auto", True)),
                    "min_word_len": int(item.get("min_word_len", 4)),
                }
            )
            continue

        if source_type == "managed_ref":
            ref = str(item.get("ref", "")).strip()
            if not ref:
                raise ValueError(f"options.aliasing.sources[{idx}].ref is required for type=managed_ref")
            out.append({"type": "managed_ref", "ref": ref})
            continue

        raise ValueError(
            f"options.aliasing.sources[{idx}].type must be one of inline, field, acronym, managed_ref"
        )
    return out
