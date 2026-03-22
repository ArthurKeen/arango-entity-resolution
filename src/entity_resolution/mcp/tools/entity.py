"""
Entity-level MCP tools: resolve_entity and explain_match.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import jellyfish
from arango import ArangoClient
from entity_resolution.mcp.contracts import CrossCollectionRequest, ResolveEntityRequest
from entity_resolution.mcp.connection import get_arango_hosts

ER_OPTIONS_SCHEMA_VERSION = "1.0"


def run_resolve_entity(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection: str,
    record: Dict[str, Any],
    fields: List[str],
    confidence_threshold: float = 0.85,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Find existing records in *collection* that match *record*.

    Runs blocking + similarity for this single record only — does **not**
    modify the database.  Returns a ranked list of candidate matches.
    """
    request = ResolveEntityRequest(
        collection=collection,
        record=record,
        fields=fields,
        confidence_threshold=confidence_threshold,
        top_k=top_k,
    )
    return run_resolve_entity_request(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        request=request,
    )


def run_resolve_entity_request(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    request: ResolveEntityRequest,
) -> List[Dict[str, Any]]:
    """Resolve entity matches from a canonical normalized request object."""
    from entity_resolution.core.incremental_resolver import IncrementalResolver

    client = ArangoClient(hosts=get_arango_hosts(host, port))
    db = client.db(database, username=username, password=password)

    resolver = IncrementalResolver(
        db=db,
        collection=request.collection,
        fields=request.fields,
        confidence_threshold=request.confidence_threshold,
    )
    matches = resolver.resolve(request.record, top_k=request.top_k)
    return matches


def run_explain_match(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection: str,
    key_a: str,
    key_b: str,
    fields: List[str] | None = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return a field-level similarity breakdown explaining why (or why not)
    two entity documents match.
    """

    client = ArangoClient(hosts=get_arango_hosts(host, port))
    db = client.db(database, username=username, password=password)

    coll = db.collection(collection)
    doc_a = coll.get(key_a)
    doc_b = coll.get(key_b)

    if doc_a is None:
        return {"error": f"Document '{key_a}' not found in {collection}"}
    if doc_b is None:
        return {"error": f"Document '{key_b}' not found in {collection}"}

    # Use caller-supplied fields or compare all shared string fields
    compare_fields = fields or [
        k for k in set(doc_a.keys()) & set(doc_b.keys())
        if not k.startswith("_") and isinstance(doc_a[k], str)
    ]

    field_scores: Dict[str, Any] = {}
    scores: List[float] = []

    for field in compare_fields:
        val_a = str(doc_a.get(field, "") or "")
        val_b = str(doc_b.get(field, "") or "")

        if not val_a and not val_b:
            continue

        jw = jellyfish.jaro_winkler_similarity(val_a, val_b)
        exact = 1.0 if val_a.lower() == val_b.lower() else 0.0

        score = max(jw, exact)
        scores.append(score)
        field_scores[field] = {
            "value_a": val_a,
            "value_b": val_b,
            "score": round(score, 4),
            "method": "exact" if exact == 1.0 else "jaro_winkler",
        }

    overall = round(sum(scores) / len(scores), 4) if scores else 0.0

    # Check if there's an existing edge between them
    edge_coll = f"{collection}_similarity_edges"
    existing_edge = None
    if db.has_collection(edge_coll):
        cursor = db.aql.execute(
            """
            FOR e IN @@ec
              FILTER (e._from == @fa AND e._to == @tb)
                  OR (e._from == @fb AND e._to == @ta)
              LIMIT 1
              RETURN {confidence: e.confidence, method: e.method}
            """,
            bind_vars={
                "@ec": edge_coll,
                "fa": f"{collection}/{key_a}",
                "tb": f"{collection}/{key_b}",
                "fb": f"{collection}/{key_b}",
                "ta": f"{collection}/{key_a}",
            },
        )
        edges = list(cursor)
        if edges:
            existing_edge = edges[0]

    payload = {
        "er_options_schema_version": ER_OPTIONS_SCHEMA_VERSION,
        "key_a": key_a,
        "key_b": key_b,
        "overall_score": overall,
        "field_breakdown": field_scores,
        "fields_compared": len(field_scores),
        "existing_edge": existing_edge,
        "interpretation": (
            "strong match" if overall >= 0.90
            else "probable match" if overall >= 0.75
            else "uncertain" if overall >= 0.55
            else "likely different"
        ),
    }
    if isinstance(options, dict):
        payload["gates"] = _build_explain_gates(
            doc_a=doc_a,
            doc_b=doc_b,
            compare_fields=compare_fields,
            overall_score=overall,
            options=options,
        )
    return payload


def _build_explain_gates(
    *,
    doc_a: Dict[str, Any],
    doc_b: Dict[str, Any],
    compare_fields: List[str],
    overall_score: float,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    similarity = options.get("similarity") if isinstance(options.get("similarity"), dict) else {}
    gating = options.get("gating") if isinstance(options.get("gating"), dict) else {}

    similarity_type = str(similarity.get("type", "default") or "default").strip().lower()
    score_threshold = float(similarity.get("confidence_threshold", 0.0))
    token_jaccard_min_score = float(similarity.get("token_jaccard_min_score", 0.0))
    token_jaccard_fields_raw = similarity.get("token_jaccard_fields", [])
    token_jaccard_fields = [str(f).strip() for f in token_jaccard_fields_raw] if isinstance(token_jaccard_fields_raw, list) else []
    min_margin = float(gating.get("min_margin", 0.0))
    gating_mode = str(gating.get("mode", "enforce") or "enforce").strip().lower()
    if gating_mode not in {"enforce", "report_only", "shadow"}:
        gating_mode = "enforce"
    require_token_overlap = bool(gating.get("require_token_overlap", False))
    token_overlap_bypass_score = float(gating.get("token_overlap_bypass_score", 1.0))
    target_type_field = str(gating.get("target_type_field", "type"))
    stopwords_raw = gating.get("word_index_stopwords", [])
    stopwords = [str(s).lower() for s in stopwords_raw] if isinstance(stopwords_raw, list) else []
    affinity = _normalize_affinity(gating.get("token_type_affinity"))
    alias_profile = _normalize_aliasing_profile(options.get("aliasing"))

    token_fields = _merge_unique_fields(token_jaccard_fields, compare_fields)
    source_tokens = _tokens_from_doc(doc_a, token_fields, stopwords, alias_profile=alias_profile)
    target_tokens = _tokens_from_doc(doc_b, token_fields, stopwords, alias_profile=alias_profile)
    overlap_tokens = sorted(source_tokens & target_tokens)
    candidate_type = str(doc_b.get(target_type_field, "") or "")
    token_jaccard_score = _jaccard_tokens(source_tokens, target_tokens)
    effective_token_jaccard_min_score = token_jaccard_min_score if token_jaccard_min_score > 0.0 else score_threshold

    gate_failures: List[Dict[str, Any]] = []

    if similarity_type == "token_jaccard" and token_jaccard_score < effective_token_jaccard_min_score:
        gate_failures.append(
            {
                "gate": "token_jaccard",
                "reason": "BELOW_TOKEN_JACCARD_THRESHOLD",
                "details": {
                    "token_jaccard_score": round(token_jaccard_score, 4),
                    "threshold": round(effective_token_jaccard_min_score, 4),
                    "fields": token_fields,
                },
            }
        )

    threshold_pass = overall_score >= score_threshold if score_threshold > 0.0 else True
    if not threshold_pass:
        gate_failures.append(
            {
                "gate": "score_threshold",
                "reason": "BELOW_CONFIDENCE_THRESHOLD",
                "details": {"score": overall_score, "threshold": score_threshold},
            }
        )

    margin_status = "not_evaluated"
    if min_margin > 0.0:
        gate_failures.append(
            {
                "gate": "margin",
                "reason": "MARGIN_NOT_EVALUATED_FOR_PAIR_EXPLANATION",
                "details": {"requested_min_margin": min_margin},
            }
        )

    overlap_pass = True
    if require_token_overlap and overall_score < token_overlap_bypass_score:
        overlap_pass = bool(overlap_tokens)
        if not overlap_pass:
            gate_failures.append(
                {
                    "gate": "token_overlap",
                    "reason": "NO_SHARED_TOKENS",
                    "details": {
                        "bypass_score": token_overlap_bypass_score,
                        "score": overall_score,
                    },
                }
            )

    type_affinity_pass = True
    matched_token_rules: Dict[str, List[str]] = {}
    if affinity:
        for tok in source_tokens:
            if tok in affinity:
                matched_token_rules[tok] = list(affinity[tok])
        if matched_token_rules:
            allowed_sets = [set(v) for v in matched_token_rules.values()]
            type_affinity_pass = bool(candidate_type) and any(candidate_type in s for s in allowed_sets)
            if not type_affinity_pass:
                gate_failures.append(
                    {
                        "gate": "type_affinity",
                        "reason": "TYPE_NOT_ALLOWED_FOR_CONTEXT_TOKENS",
                        "details": {
                            "candidate_type": candidate_type,
                            "target_type_field": target_type_field,
                            "matched_token_rules": matched_token_rules,
                        },
                    }
                )

    return {
        "summary": {
            "mode": gating_mode,
            "enforcement_enabled": gating_mode == "enforce",
            "all_passed": len(gate_failures) == 0,
            "gate_failures": gate_failures,
        },
        "score_threshold": {
            "configured": score_threshold > 0.0,
            "pass": threshold_pass,
            "threshold": score_threshold,
            "score": overall_score,
        },
        "token_jaccard": {
            "configured": similarity_type == "token_jaccard",
            "pass": token_jaccard_score >= effective_token_jaccard_min_score,
            "similarity_type": similarity_type,
            "fields": token_fields,
            "score": round(token_jaccard_score, 4),
            "threshold": round(effective_token_jaccard_min_score, 4),
        },
        "margin": {
            "configured": min_margin > 0.0,
            "status": margin_status,
            "requested_min_margin": min_margin,
        },
        "token_overlap": {
            "configured": require_token_overlap,
            "pass": overlap_pass,
            "bypass_score": token_overlap_bypass_score,
            "shared_tokens": overlap_tokens,
        },
        "type_affinity": {
            "configured": bool(affinity),
            "pass": type_affinity_pass,
            "target_type_field": target_type_field,
            "candidate_type": candidate_type,
            "matched_token_rules": matched_token_rules,
        },
        "aliasing": {
            "configured": bool(alias_profile.get("inline_map") or alias_profile.get("field_sources") or alias_profile.get("acronym_auto")),
            "inline_alias_count": len(alias_profile.get("inline_map", {})),
            "field_sources": alias_profile.get("field_sources", []),
            "acronym_auto": bool(alias_profile.get("acronym_auto", False)),
            "acronym_min_word_len": int(alias_profile.get("acronym_min_word_len", 4)),
            "managed_ref_requested": alias_profile.get("managed_ref_requested", []),
            "managed_ref_applied": alias_profile.get("managed_ref_applied", []),
            "managed_ref_missing": alias_profile.get("managed_ref_missing", []),
        },
    }


def _tokens_from_doc(
    doc: Dict[str, Any],
    fields: List[str],
    stopwords: List[str],
    *,
    alias_profile: Dict[str, Any],
) -> set[str]:
    sw = set(stopwords)
    tokens: set[str] = set()
    all_fields = _merge_unique_fields(fields, alias_profile.get("field_sources", []))
    for field in all_fields:
        val = doc.get(field)
        if isinstance(val, str):
            raw = re.findall(r"[A-Za-z0-9]+", val.lower())
            tokens |= {t for t in raw if t and t not in sw}
            if alias_profile.get("acronym_auto", False):
                words = [t for t in raw if len(t) >= max(1, int(alias_profile.get("acronym_min_word_len", 4)))]
                if len(words) >= 2:
                    tokens.add("".join(w[0] for w in words))
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    raw = re.findall(r"[A-Za-z0-9]+", item.lower())
                    tokens |= {t for t in raw if t and t not in sw}
                    if alias_profile.get("acronym_auto", False):
                        words = [t for t in raw if len(t) >= max(1, int(alias_profile.get("acronym_min_word_len", 4)))]
                        if len(words) >= 2:
                            tokens.add("".join(w[0] for w in words))
    tokens = _expand_tokens_with_alias_map(tokens, alias_profile.get("inline_map", {}))
    return tokens


def _normalize_affinity(value: Any) -> Dict[str, List[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        return {}
    out: Dict[str, List[str]] = {}
    for token, raw in value.items():
        key = str(token).strip().lower()
        if not key:
            continue
        if isinstance(raw, list):
            vals = [str(v).strip() for v in raw if str(v).strip()]
        elif isinstance(raw, dict):
            allowed = raw.get("allowed_types", [])
            vals = [str(v).strip() for v in allowed if str(v).strip()] if isinstance(allowed, list) else []
        else:
            vals = []
        if vals:
            out[key] = vals
    return out


def _normalize_aliasing_profile(value: Any) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "inline_map": {},
        "field_sources": [],
        "acronym_auto": False,
        "acronym_min_word_len": 4,
        "managed_ref_requested": [],
        "managed_ref_applied": [],
        "managed_ref_missing": [],
    }
    if not isinstance(value, dict):
        return profile
    sources = value.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("options.aliasing.sources must be an array/list when provided")
    managed = value.get("managed_refs", {})
    if managed is not None and not isinstance(managed, dict):
        raise ValueError("options.aliasing.managed_refs must be an object/dict when provided")
    if isinstance(managed, dict):
        for ref_id, ref_map in managed.items():
            ref = str(ref_id).strip()
            if not ref:
                continue
            if not isinstance(ref_map, dict):
                raise ValueError(f"options.aliasing.managed_refs.{ref} must be an object/dict")
    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"options.aliasing.sources[{idx}] must be an object/dict")
        source_type = str(source.get("type", "")).strip().lower()
        if not source_type:
            raise ValueError(f"options.aliasing.sources[{idx}].type is required")
        if source_type == "inline":
            raw_map = source.get("map", {})
            if not isinstance(raw_map, dict):
                raise ValueError(f"options.aliasing.sources[{idx}].map must be an object/dict")
            _merge_alias_map(profile["inline_map"], raw_map)
        elif source_type == "field":
            field = str(source.get("field", "")).strip()
            if not field:
                raise ValueError(f"options.aliasing.sources[{idx}].field is required for type=field")
            profile["field_sources"].append(field)
        elif source_type == "acronym":
            if bool(source.get("auto", True)):
                profile["acronym_auto"] = True
            profile["acronym_min_word_len"] = int(source.get("min_word_len", 4))
        elif source_type == "managed_ref":
            ref = str(source.get("ref", "")).strip()
            if not ref:
                raise ValueError(f"options.aliasing.sources[{idx}].ref is required for type=managed_ref")
            profile["managed_ref_requested"].append(ref)
            ref_map = managed.get(ref) if isinstance(managed, dict) else None
            if isinstance(ref_map, dict):
                _merge_alias_map(profile["inline_map"], ref_map)
                profile["managed_ref_applied"].append(ref)
            else:
                profile["managed_ref_missing"].append(ref)
        else:
            raise ValueError(
                f"options.aliasing.sources[{idx}].type must be one of inline, field, acronym, managed_ref"
            )
    profile["field_sources"] = _merge_unique_fields(profile["field_sources"], [])
    profile["managed_ref_requested"] = _merge_unique_fields(profile["managed_ref_requested"], [])
    profile["managed_ref_applied"] = _merge_unique_fields(profile["managed_ref_applied"], [])
    profile["managed_ref_missing"] = _merge_unique_fields(profile["managed_ref_missing"], [])
    return profile


def _expand_tokens_with_alias_map(tokens: set[str], inline_map: Dict[str, list[str]]) -> set[str]:
    if not inline_map:
        return tokens
    expanded = set(tokens)
    for tok in list(tokens):
        for mapped in inline_map.get(tok, []):
            if mapped:
                expanded.add(mapped)
    return expanded


def _merge_unique_fields(primary: List[str], extra: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in list(primary or []) + list(extra or []):
        val = str(raw).strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def _merge_alias_map(target: Dict[str, List[str]], value: Any) -> None:
    if not isinstance(value, dict):
        return
    for key, vals in value.items():
        token = str(key).strip().lower()
        if not token:
            continue
        if isinstance(vals, list):
            mapped = [str(v).strip().lower() for v in vals if str(v).strip()]
        else:
            mapped = [str(vals).strip().lower()] if str(vals).strip() else []
        if not mapped:
            continue
        existing = target.get(token, [])
        target[token] = _merge_unique_fields(existing, mapped)


def _jaccard_tokens(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return float(len(tokens_a & tokens_b)) / float(len(union))


def run_resolve_entity_cross_collection(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    source_collection: str,
    target_collection: str,
    source_fields: List[str],
    target_fields: List[str],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Legacy entry point — delegates to the request-based handler."""
    from entity_resolution.mcp.normalization import normalize_cross_collection_args

    req = normalize_cross_collection_args(
        source_collection=source_collection,
        target_collection=target_collection,
        source_fields=source_fields,
        target_fields=target_fields,
        options=options,
    )
    return run_resolve_cross_collection_request(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        request=req,
    )


def run_resolve_cross_collection_request(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    request: CrossCollectionRequest,
) -> Dict[str, Any]:
    """Execute cross-collection entity linking from a normalized request."""
    from entity_resolution.services.cross_collection_matching_service import CrossCollectionMatchingService

    custom_filters: Dict[str, Any] = {}
    if request.target_filter is not None:
        custom_filters["target"] = request.target_filter
    if request.source_skip_values is not None:
        source_filter: Dict[str, Dict[str, Any]] = {}
        for field_name, values in request.source_skip_values.items():
            vals = values if isinstance(values, list) else [values]
            source_filter[str(field_name)] = {"not_equal": list(vals)}
        if source_filter:
            custom_filters["source"] = source_filter

    client = ArangoClient(hosts=get_arango_hosts(host, port))
    db = client.db(database, username=username, password=password)

    service = CrossCollectionMatchingService(
        db=db,
        source_collection=request.source_collection,
        target_collection=request.target_collection,
        edge_collection=request.edge_collection
        or f"{request.source_collection}_{request.target_collection}_resolved_edges",
        search_view=request.search_view,
    )

    service.configure_matching(
        source_fields=request.source_fields,
        target_fields=request.target_fields,
        field_weights=request.field_weights,
        blocking_fields=request.blocking_fields,
        blocking_strategy=request.blocking_strategy,
        custom_filters=custom_filters,
    )

    stats = service.match_entities(
        threshold=request.confidence_threshold,
        batch_size=request.batch_size,
        limit=request.candidate_limit,
        use_bm25=request.use_bm25,
        bm25_weight=request.bm25_weight,
        mark_as_inferred=True,
        max_runtime_seconds=max(1.0, request.max_runtime_ms / 1000.0),
        deterministic_tiebreak=request.deterministic_tiebreak,
    )

    result: Dict[str, Any] = {
        "source_collection": request.source_collection,
        "target_collection": request.target_collection,
        "edge_collection": request.edge_collection,
        "execution_guardrails": {
            "candidate_limit": request.candidate_limit,
            "batch_size": request.batch_size,
            "max_runtime_ms": request.max_runtime_ms,
            "deterministic_tiebreak": request.deterministic_tiebreak,
        },
        "stats": stats,
    }
    if request.return_diagnostics:
        result["diagnostics"] = {
            "source_fields": request.source_fields,
            "target_fields": request.target_fields,
            "blocking_fields": request.blocking_fields,
            "blocking_strategy": request.blocking_strategy,
            "confidence_threshold": request.confidence_threshold,
            "use_bm25": request.use_bm25,
        }
    return result
