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

    score_threshold = float(similarity.get("confidence_threshold", 0.0))
    min_margin = float(gating.get("min_margin", 0.0))
    require_token_overlap = bool(gating.get("require_token_overlap", False))
    token_overlap_bypass_score = float(gating.get("token_overlap_bypass_score", 1.0))
    target_type_field = str(gating.get("target_type_field", "type"))
    stopwords_raw = gating.get("word_index_stopwords", [])
    stopwords = [str(s).lower() for s in stopwords_raw] if isinstance(stopwords_raw, list) else []
    affinity = _normalize_affinity(gating.get("token_type_affinity"))

    source_tokens = _tokens_from_doc(doc_a, compare_fields, stopwords)
    target_tokens = _tokens_from_doc(doc_b, compare_fields, stopwords)
    overlap_tokens = sorted(source_tokens & target_tokens)
    candidate_type = str(doc_b.get(target_type_field, "") or "")

    gate_failures: List[Dict[str, Any]] = []

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
            "all_passed": len(gate_failures) == 0,
            "gate_failures": gate_failures,
        },
        "score_threshold": {
            "configured": score_threshold > 0.0,
            "pass": threshold_pass,
            "threshold": score_threshold,
            "score": overall_score,
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
    }


def _tokens_from_doc(doc: Dict[str, Any], fields: List[str], stopwords: List[str]) -> set[str]:
    sw = set(stopwords)
    tokens: set[str] = set()
    for field in fields:
        val = doc.get(field)
        if isinstance(val, str):
            raw = re.findall(r"[A-Za-z0-9]+", val.lower())
            tokens |= {t for t in raw if t and t not in sw}
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    raw = re.findall(r"[A-Za-z0-9]+", item.lower())
                    tokens |= {t for t in raw if t and t not in sw}
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
