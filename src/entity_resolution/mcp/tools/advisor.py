"""
Advisor-level MCP tools: dataset profiling and blocking recommendations.
"""
from __future__ import annotations

import math
import json
import hashlib
from collections import Counter
from itertools import combinations
from typing import Any, Dict, List, Optional

import yaml
from arango import ArangoClient
from entity_resolution.mcp.connection import get_arango_hosts

TOOL_VERSION = "1.0.0"
ADVISOR_POLICY_VERSION = "2026-03-01"
ER_OPTIONS_SCHEMA_VERSION = "1.0"


def _get_db(host: str, port: int, username: str, password: str, database: str):
    client = ArangoClient(hosts=get_arango_hosts(host, port))
    return client.db(database, username=username, password=password)


def run_profile_dataset(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    source_type: str,
    dataset_id: str,
    sample_limit: int = 10000,
    request_id: Optional[str] = None,
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    compute_pairwise_signals: bool = True,
) -> Dict[str, Any]:
    """Profile dataset fields and return ER-relevant summary signals."""
    if source_type != "collection":
        raise ValueError("Only source_type='collection' is currently supported")

    db = _get_db(host, port, username, password, database)
    if not db.has_collection(dataset_id):
        raise ValueError(f"Collection not found: {dataset_id}")

    sample_limit = max(100, int(sample_limit))
    row_count_estimate = db.collection(dataset_id).count()

    cursor = db.aql.execute(
        """
        FOR d IN @@coll
          LIMIT @limit
          RETURN d
        """,
        bind_vars={"@coll": dataset_id, "limit": sample_limit},
    )
    docs = list(cursor)

    field_names = _discover_fields(docs, include_fields=include_fields, exclude_fields=exclude_fields)
    field_profiles = []
    for field in field_names:
        field_profiles.append(_profile_field(docs, field))

    pairwise_signals = {}
    if compute_pairwise_signals:
        pairwise_signals = _pairwise_signals(docs, field_profiles)

    result = {
        "profile_id": f"profile_{dataset_id}",
        "row_count_estimate": row_count_estimate,
        "sample_size": len(docs),
        "field_profiles": field_profiles,
        "pairwise_signals": pairwise_signals,
    }
    return _ok(result=result, request_id=request_id)


def run_recommend_blocking_candidates(
    *,
    profile: Dict[str, Any],
    request_id: Optional[str] = None,
    max_composite_size: int = 3,
    max_results: int = 20,
    must_include_fields: Optional[List[str]] = None,
    must_exclude_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Rank blocking candidates from a profile payload."""
    field_profiles = profile.get("field_profiles") or []
    if not field_profiles:
        return _ok(result={"blocking_candidates": []}, request_id=request_id)

    excluded = set(must_exclude_fields or [])
    must_include = list(must_include_fields or [])

    base_fields: List[Dict[str, Any]] = []
    for fp in field_profiles:
        field = fp.get("field")
        if not field or field in excluded:
            continue
        if fp.get("data_type") != "string":
            continue
        if float(fp.get("null_rate", 1.0)) > 0.5:
            continue
        base_fields.append(fp)

    scored_candidates = []
    max_size = max(1, min(5, int(max_composite_size)))
    max_results = max(1, int(max_results))

    # Include single-field candidates and composites up to max size.
    name_to_profile = {fp["field"]: fp for fp in base_fields if fp.get("field")}
    base_field_names = list(name_to_profile.keys())
    for size in range(1, max_size + 1):
        for fields in combinations(base_field_names, size):
            if any(f not in fields for f in must_include):
                continue
            score = _blocking_fit_score([name_to_profile[f] for f in fields])
            scored_candidates.append(
                {
                    "candidate_id": "_".join(fields),
                    "fields": list(fields),
                    "fit_score": round(score, 4),
                    "estimated_candidate_pairs": _estimate_candidate_pairs(profile, fields),
                    "estimated_recall_proxy": _estimate_recall_proxy(fields),
                    "estimated_precision_proxy": _estimate_precision_proxy(fields),
                    "hub_risk_score": _estimate_hub_risk(profile, fields),
                    "notes": _candidate_notes(fields),
                }
            )

    scored_candidates.sort(key=lambda c: c["fit_score"], reverse=True)
    return _ok(result={"blocking_candidates": scored_candidates[:max_results]}, request_id=request_id)


def run_recommend_resolution_strategy(
    *,
    profile: Dict[str, Any],
    objective_profile: Dict[str, Any],
    request_id: Optional[str] = None,
    allow_embedding_models: bool = True,
    allow_graph_clustering: bool = True,
) -> Dict[str, Any]:
    """Recommend ranked ER strategy families from profile + objectives."""
    objective = objective_profile or {}
    priority = str(objective.get("priority", "balanced"))
    target = _objective_target_weights(priority)

    near_dup_rate = float((profile.get("pairwise_signals") or {}).get("near_duplicate_rate_estimate", 0.0))
    hub_risk = float((profile.get("pairwise_signals") or {}).get("hub_risk_score", 0.0))
    row_count = int(profile.get("row_count_estimate", 0) or 0)
    sample_size = int(profile.get("sample_size", 0) or 0)
    field_profiles = profile.get("field_profiles") or []
    string_fields = [fp for fp in field_profiles if fp.get("data_type") == "string"]
    avg_entropy = (
        sum(float(fp.get("entropy_estimate", 0.0)) for fp in string_fields) / len(string_fields)
        if string_fields
        else 0.0
    )
    avg_null = (
        sum(float(fp.get("null_rate", 1.0)) for fp in string_fields) / len(string_fields)
        if string_fields
        else 1.0
    )

    candidates = _strategy_catalog(
        allow_embedding_models=allow_embedding_models,
        allow_graph_clustering=allow_graph_clustering,
    )
    if not candidates:
        return _ok(result={"recommendations": []}, request_id=request_id)

    scored: List[Dict[str, Any]] = []
    for strategy in candidates:
        strengths = strategy["strengths"]
        objective_fit = sum(target.get(k, 0.0) * strengths.get(k, 0.0) for k in target.keys())
        signal_adjustment = _signal_adjustment(
            strategy_id=strategy["strategy_id"],
            strengths=strengths,
            near_dup_rate=near_dup_rate,
            hub_risk=hub_risk,
            avg_entropy=avg_entropy,
            avg_null=avg_null,
            row_count=row_count,
        )
        constraint_adjustment = _constraint_adjustment(strengths=strengths, objective=objective, row_count=row_count)
        fit_score = max(0.0, min(1.0, objective_fit + signal_adjustment + constraint_adjustment))

        scored.append(
            {
                "strategy_id": strategy["strategy_id"],
                "fit_score": round(fit_score, 4),
                "expected_tradeoffs": strategy["expected_tradeoffs"],
                "rationale": _build_strategy_rationale(
                    strategy_id=strategy["strategy_id"],
                    objective_priority=priority,
                    near_dup_rate=near_dup_rate,
                    hub_risk=hub_risk,
                    avg_entropy=avg_entropy,
                ),
            }
        )

    scored.sort(key=lambda item: item["fit_score"], reverse=True)
    recommendations: List[Dict[str, Any]] = []
    for idx, item in enumerate(scored):
        next_score = scored[idx + 1]["fit_score"] if idx + 1 < len(scored) else item["fit_score"]
        confidence = _recommendation_confidence(
            fit_score=float(item["fit_score"]),
            score_gap=max(0.0, float(item["fit_score"]) - float(next_score)),
            sample_size=sample_size,
            has_pairwise=bool(profile.get("pairwise_signals")),
            string_field_count=len(string_fields),
            objective_has_constraints=any(
                k in objective
                for k in ("latency_budget_ms", "throughput_target_rps", "max_memory_mb", "max_candidate_pairs", "max_edge_count")
            ),
        )
        recommendations.append(
            {
                "strategy_id": item["strategy_id"],
                "rank": idx + 1,
                "fit_score": item["fit_score"],
                "expected_tradeoffs": item["expected_tradeoffs"],
                "rationale": item["rationale"],
                "confidence": confidence,
            }
        )

    return _ok(result={"recommendations": recommendations}, request_id=request_id)


def run_estimate_feature_weights(
    *,
    feature_matrix_ref: Dict[str, Any],
    target_metric: str = "f1",
    min_samples: int = 1000,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Estimate feature weights from labeled pairwise samples."""
    min_samples = max(100, int(min_samples))
    rows = _extract_labeled_rows(feature_matrix_ref)
    if len(rows) < min_samples:
        return _error(
            code="NOT_ENOUGH_DATA",
            message="Minimum sample requirement not met",
            details={"samples_found": len(rows), "min_samples": min_samples},
            request_id=request_id,
        )

    positives = [row for row in rows if row["label"] == 1]
    negatives = [row for row in rows if row["label"] == 0]
    if not positives or not negatives:
        return _error(
            code="INVALID_ARGUMENT",
            message="Both positive and negative labeled samples are required",
            details={"positives": len(positives), "negatives": len(negatives)},
            request_id=request_id,
        )

    feature_names = sorted({k for row in rows for k in row["features"].keys()})
    if not feature_names:
        return _error(
            code="INVALID_ARGUMENT",
            message="No numeric features found in feature_matrix_ref",
            details={},
            request_id=request_id,
        )

    raw_scores: Dict[str, float] = {}
    for feature in feature_names:
        pos_vals = [row["features"][feature] for row in positives if feature in row["features"]]
        neg_vals = [row["features"][feature] for row in negatives if feature in row["features"]]
        if not pos_vals or not neg_vals:
            continue
        separation = _feature_separation_score(pos_vals, neg_vals)
        raw_scores[feature] = max(0.0, separation)

    if not raw_scores:
        return _error(
            code="INVALID_ARGUMENT",
            message="Could not compute separability scores from provided features",
            details={},
            request_id=request_id,
        )

    weights = _normalize_weights(raw_scores)
    threshold = _recommend_match_threshold(rows, weights, target_metric=target_metric)
    metric_estimate = _estimate_target_metric(rows, weights, threshold, target_metric=target_metric)
    confidence = _weights_confidence(
        sample_size=len(rows),
        positive_count=len(positives),
        feature_count=len(weights),
        metric_estimate=metric_estimate,
    )

    result = {
        "weights": weights,
        "threshold_recommendation": {
            "match_threshold": round(threshold, 4),
            "review_band": [round(max(0.0, threshold - 0.12), 4), round(threshold, 4)],
        },
        "diagnostics": {
            "samples_used": len(rows),
            "positive_samples": len(positives),
            "negative_samples": len(negatives),
            "target_metric": target_metric,
            "target_metric_estimate": round(metric_estimate, 4),
        },
        "confidence": confidence,
    }
    return _ok(result=result, request_id=request_id)


def run_simulate_pipeline_variants(
    *,
    variants: List[Dict[str, Any]],
    objective_profile: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Simulate multiple pipeline variants and return ranked outcomes."""
    if len(variants) < 2:
        return _error(
            code="INVALID_ARGUMENT",
            message="At least two variants are required",
            details={"variants_provided": len(variants), "min_required": 2},
            request_id=request_id,
        )

    objective = objective_profile or {}
    priority = str(objective.get("priority", "balanced"))
    weights = _objective_target_weights(priority)

    variant_results: List[Dict[str, Any]] = []
    ranking_inputs: List[Dict[str, Any]] = []
    for raw_variant in variants:
        variant_id = str(raw_variant.get("variant_id", "")).strip()
        config = raw_variant.get("config")
        if not variant_id or not isinstance(config, dict):
            return _error(
                code="INVALID_ARGUMENT",
                message="Each variant must include variant_id and config object",
                details={"invalid_variant": raw_variant},
                request_id=request_id,
            )

        metrics = _estimate_variant_metrics(config)
        fit_score = _variant_fit_score(metrics=metrics, objective=objective, objective_weights=weights)
        variant_results.append(
            {
                "variant_id": variant_id,
                "estimated_runtime_sec": metrics["estimated_runtime_sec"],
                "estimated_peak_memory_mb": metrics["estimated_peak_memory_mb"],
                "estimated_precision": metrics["estimated_precision"],
                "estimated_recall": metrics["estimated_recall"],
                "estimated_storage_mb": metrics["estimated_storage_mb"],
            }
        )
        ranking_inputs.append(
            {
                "variant_id": variant_id,
                "fit_score": fit_score,
                "metrics": metrics,
            }
        )

    ranking_inputs.sort(key=lambda item: item["fit_score"], reverse=True)
    ranking = [
        {"variant_id": item["variant_id"], "rank": idx + 1, "fit_score": round(item["fit_score"], 4)}
        for idx, item in enumerate(ranking_inputs)
    ]
    winner = ranking_inputs[0]
    result = {
        "variant_results": variant_results,
        "ranking": ranking,
        "winner": {
            "variant_id": winner["variant_id"],
            "reason": _winner_reason(metrics=winner["metrics"], objective=objective, priority=priority),
        },
    }
    return _ok(result=result, request_id=request_id)


def run_export_recommended_config(
    *,
    recommendation: Dict[str, Any],
    format: str,
    include_rationale: bool = True,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Export a normalized ER config artifact from advisor recommendations."""
    output_format = str(format).strip().lower()
    if output_format not in {"json", "yaml"}:
        return _error(
            code="INVALID_ARGUMENT",
            message="format must be one of: json, yaml",
            details={"format": format, "supported_formats": ["json", "yaml"]},
            request_id=request_id,
        )

    if not isinstance(recommendation, dict):
        return _error(
            code="INVALID_ARGUMENT",
            message="recommendation must be an object",
            details={},
            request_id=request_id,
        )

    normalized = _build_export_config(
        recommendation=recommendation,
        include_rationale=include_rationale,
    )

    if output_format == "json":
        config_text = json.dumps(normalized, indent=2, sort_keys=True)
    else:
        config_text = yaml.safe_dump(normalized, sort_keys=True)

    digest = hashlib.sha256(config_text.encode("utf-8")).hexdigest()
    result = {
        "format": output_format,
        "config_text": config_text,
        "config_hash": f"sha256:{digest}",
        "policy_version": ADVISOR_POLICY_VERSION,
    }
    return _ok(result=result, request_id=request_id)


def run_evaluate_blocking_plan(
    *,
    profile: Dict[str, Any],
    blocking_plan: Dict[str, Any],
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate a proposed blocking plan and return risk/guardrail guidance."""
    if not isinstance(blocking_plan, dict):
        return _error(
            code="INVALID_ARGUMENT",
            message="blocking_plan must be an object",
            details={},
            request_id=request_id,
        )

    fields = blocking_plan.get("fields")
    if not isinstance(fields, list) or not fields:
        return _error(
            code="INVALID_ARGUMENT",
            message="blocking_plan.fields must be a non-empty array",
            details={},
            request_id=request_id,
        )
    normalized_fields = [str(f).strip() for f in fields if str(f).strip()]
    if not normalized_fields:
        return _error(
            code="INVALID_ARGUMENT",
            message="blocking_plan.fields must include at least one valid field",
            details={},
            request_id=request_id,
        )

    profile_fields = {
        str(fp.get("field")): fp
        for fp in (profile.get("field_profiles") or [])
        if isinstance(fp, dict) and fp.get("field")
    }
    unknown_fields = [f for f in normalized_fields if f not in profile_fields]
    if unknown_fields:
        return _error(
            code="INVALID_ARGUMENT",
            message=f"Unknown field(s) in blocking_plan.fields: {', '.join(unknown_fields)}",
            details={"unknown_fields": unknown_fields},
            request_id=request_id,
        )

    min_block_size = int(blocking_plan.get("min_block_size", 2) or 2)
    max_block_size = int(blocking_plan.get("max_block_size", 1000) or 1000)
    min_block_size = max(1, min_block_size)
    max_block_size = max(min_block_size, max_block_size)

    row_count = max(1, int(profile.get("row_count_estimate", 0) or 0))
    field_profiles = [profile_fields[f] for f in normalized_fields if f in profile_fields]
    avg_entropy = (
        sum(float(fp.get("entropy_estimate", 0.0)) for fp in field_profiles) / len(field_profiles)
        if field_profiles
        else 0.0
    )
    avg_null_rate = (
        sum(float(fp.get("null_rate", 1.0)) for fp in field_profiles) / len(field_profiles)
        if field_profiles
        else 1.0
    )
    pairwise = profile.get("pairwise_signals") or {}
    hub_risk = float(pairwise.get("hub_risk_score", 0.0))

    reduction_strength = _clamp(0.18 + 0.28 * avg_entropy + 0.08 * max(0, len(normalized_fields) - 1), 0.08, 0.9)
    reduction_strength *= _clamp(1.0 - (avg_null_rate * 0.55), 0.3, 1.0)

    estimated_block_count = max(1, int(row_count * reduction_strength))
    estimated_pairs_per_block = max(
        float(min_block_size),
        _clamp(max_block_size * (1.0 - reduction_strength * 0.72), float(min_block_size), float(max_block_size)),
    )
    estimated_candidate_pairs = int(estimated_block_count * estimated_pairs_per_block)

    p50 = int(_clamp(min_block_size + (estimated_pairs_per_block * 0.35), float(min_block_size), float(max_block_size)))
    p90 = int(_clamp(min_block_size + (estimated_pairs_per_block * 0.9), float(min_block_size), float(max_block_size)))
    p99 = int(_clamp(min_block_size + (estimated_pairs_per_block * 1.6), float(min_block_size), float(max_block_size)))
    max_estimate = int(_clamp(min_block_size + (estimated_pairs_per_block * 2.8), float(min_block_size), float(max_block_size)))

    risk_flags: List[str] = []
    if hub_risk >= 0.2:
        risk_flags.append("heavy_hitter_blocks_detected")
    if max_estimate >= max_block_size * 0.9:
        risk_flags.append("max_block_size_pressure_high")
    pair_space_ratio = estimated_candidate_pairs / float(row_count * row_count)
    if pair_space_ratio > 0.02:
        risk_flags.append("edge_explosion_risk_high")
    elif pair_space_ratio > 0.008:
        risk_flags.append("edge_explosion_risk_moderate")
    if avg_null_rate > 0.35:
        risk_flags.append("missing_data_risk_high")

    guardrail_max = int(_clamp(max_block_size * (0.6 if hub_risk >= 0.2 else 0.75), float(min_block_size + 1), float(max_block_size)))
    guardrail_min = int(_clamp(min_block_size, 1.0, float(max(2, p50 // 3))))
    result = {
        "estimated_block_count": estimated_block_count,
        "estimated_candidate_pairs": estimated_candidate_pairs,
        "estimated_block_size_distribution": {
            "p50": p50,
            "p90": p90,
            "p99": p99,
            "max_estimate": max_estimate,
        },
        "risk_flags": risk_flags,
        "recommended_guardrails": {
            "suggested_max_block_size": guardrail_max,
            "suggested_min_block_size": guardrail_min,
        },
    }
    return _ok(result=result, request_id=request_id)


def _ok(*, result: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "tool_version": TOOL_VERSION,
        "advisor_policy_version": ADVISOR_POLICY_VERSION,
        "er_options_schema_version": ER_OPTIONS_SCHEMA_VERSION,
        "request_id": request_id,
        "result": result,
    }


def _error(
    *,
    code: str,
    message: str,
    details: Dict[str, Any],
    request_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "status": "error",
        "tool_version": TOOL_VERSION,
        "er_options_schema_version": ER_OPTIONS_SCHEMA_VERSION,
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def _discover_fields(
    docs: List[Dict[str, Any]],
    include_fields: Optional[List[str]],
    exclude_fields: Optional[List[str]],
) -> List[str]:
    include = set(include_fields or [])
    exclude = set(exclude_fields or [])
    discovered: List[str] = []
    seen = set()
    for d in docs:
        for field in d.keys():
            if field.startswith("_"):
                continue
            if include and field not in include:
                continue
            if field in exclude:
                continue
            if field not in seen:
                seen.add(field)
                discovered.append(field)
    return discovered


def _profile_field(docs: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
    values = [d.get(field) for d in docs]
    non_null = [v for v in values if v is not None and not (isinstance(v, str) and not v.strip())]
    null_rate = 1.0 if not values else (len(values) - len(non_null)) / len(values)

    type_counts = Counter(type(v).__name__ for v in non_null)
    data_type = "unknown"
    if type_counts:
        top_type = type_counts.most_common(1)[0][0]
        if top_type in ("str",):
            data_type = "string"
        elif top_type in ("int", "float"):
            data_type = "number"
        elif top_type in ("bool",):
            data_type = "boolean"
        elif top_type in ("dict",):
            data_type = "object"
        elif top_type in ("list",):
            data_type = "array"
        else:
            data_type = top_type

    distinct_count = len(set(_value_key(v) for v in non_null))
    heavy_hitters = []
    if non_null:
        c = Counter(_value_key(v) for v in non_null)
        for value, cnt in c.most_common(5):
            heavy_hitters.append({"value": value, "fraction": round(cnt / len(non_null), 4)})

    entropy_estimate = _normalized_entropy([hh["fraction"] for hh in heavy_hitters])
    token_stats = _token_stats(non_null) if data_type == "string" else {"avg_token_count": None, "avg_char_length": None}

    return {
        "field": field,
        "data_type": data_type,
        "null_rate": round(null_rate, 4),
        "distinct_count_estimate": distinct_count,
        "entropy_estimate": round(entropy_estimate, 4),
        "heavy_hitters": heavy_hitters,
        "token_stats": token_stats,
    }


def _value_key(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return str(value)


def _normalized_entropy(fractions: List[float]) -> float:
    probs = [p for p in fractions if p > 0]
    if not probs:
        return 0.0
    entropy = -sum(p * math.log2(p) for p in probs)
    max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
    return min(1.0, entropy / max_entropy if max_entropy else 0.0)


def _token_stats(values: List[Any]) -> Dict[str, Any]:
    texts = [str(v) for v in values if isinstance(v, str)]
    if not texts:
        return {"avg_token_count": None, "avg_char_length": None}
    token_counts = [len(t.split()) for t in texts]
    char_lengths = [len(t) for t in texts]
    return {
        "avg_token_count": round(sum(token_counts) / len(token_counts), 2),
        "avg_char_length": round(sum(char_lengths) / len(char_lengths), 2),
    }


def _pairwise_signals(docs: List[Dict[str, Any]], field_profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not docs:
        return {"near_duplicate_rate_estimate": 0.0, "hub_risk_score": 0.0}
    string_fields = [fp["field"] for fp in field_profiles if fp.get("data_type") == "string"]
    chosen = string_fields[:2] if string_fields else []
    if not chosen:
        return {"near_duplicate_rate_estimate": 0.0, "hub_risk_score": 0.0}

    signatures = []
    for d in docs:
        parts = [str(d.get(f, "")).strip().lower() for f in chosen]
        signatures.append("|".join(parts))

    counts = Counter(signatures)
    duplicate_records = sum(cnt for cnt in counts.values() if cnt > 1)
    near_duplicate_rate = duplicate_records / len(docs)
    max_group = max(counts.values()) if counts else 0
    hub_risk = max_group / len(docs) if docs else 0.0
    return {
        "near_duplicate_rate_estimate": round(near_duplicate_rate, 4),
        "hub_risk_score": round(hub_risk, 4),
    }


def _blocking_fit_score(field_profiles: List[Dict[str, Any]]) -> float:
    # Heuristic: prefer low nulls and high entropy, lightly favor composite keys.
    if not field_profiles:
        return 0.0
    avg_null = sum(float(fp.get("null_rate", 1.0)) for fp in field_profiles) / len(field_profiles)
    avg_entropy = sum(float(fp.get("entropy_estimate", 0.0)) for fp in field_profiles) / len(field_profiles)
    composite_bonus = min(0.15, 0.05 * (len(field_profiles) - 1))
    score = (1.0 - avg_null) * 0.55 + avg_entropy * 0.30 + composite_bonus
    return max(0.0, min(1.0, score))


def _estimate_candidate_pairs(profile: Dict[str, Any], fields: tuple[str, ...]) -> int:
    row_count = int(profile.get("row_count_estimate", 0) or 0)
    # Coarse reduction model: each added field prunes pair space more.
    reduction = 0.02 if len(fields) == 1 else 0.006 if len(fields) == 2 else 0.002
    return int(max(0, row_count * row_count * reduction))


def _estimate_recall_proxy(fields: tuple[str, ...]) -> float:
    base = 0.95
    penalty = 0.07 * max(0, len(fields) - 1)
    return round(max(0.0, base - penalty), 4)


def _estimate_precision_proxy(fields: tuple[str, ...]) -> float:
    base = 0.45
    gain = 0.12 * max(0, len(fields) - 1)
    return round(min(0.99, base + gain), 4)


def _estimate_hub_risk(profile: Dict[str, Any], fields: tuple[str, ...]) -> float:
    signal = float((profile.get("pairwise_signals") or {}).get("hub_risk_score", 0.0))
    dampener = min(0.5, 0.15 * max(0, len(fields) - 1))
    return round(max(0.0, signal - dampener), 4)


def _candidate_notes(fields: tuple[str, ...]) -> List[str]:
    if len(fields) == 1:
        return ["Single-field blocking may improve recall but can increase pair volume"]
    if len(fields) == 2:
        return ["Balanced pair pruning and recall for most datasets"]
    return ["Composite key strongly prunes pair volume; validate recall impact"]


def _strategy_catalog(*, allow_embedding_models: bool, allow_graph_clustering: bool) -> List[Dict[str, Any]]:
    catalog: List[Dict[str, Any]] = [
        {
            "strategy_id": "hybrid_block_then_weighted_match",
            "strengths": {
                "precision": 0.85,
                "recall": 0.76,
                "throughput": 0.82,
                "cost": 0.78,
                "explainability": 0.73,
                "edge_control": 0.84,
                "noise_tolerance": 0.64,
            },
            "expected_tradeoffs": {
                "precision": "high",
                "recall": "medium_high",
                "throughput": "high",
                "implementation_complexity": "medium",
            },
        },
        {
            "strategy_id": "pre_ingest_canonicalize_then_match",
            "strengths": {
                "precision": 0.88,
                "recall": 0.68,
                "throughput": 0.91,
                "cost": 0.84,
                "explainability": 0.8,
                "edge_control": 0.94,
                "noise_tolerance": 0.56,
            },
            "expected_tradeoffs": {
                "precision": "high",
                "recall": "medium",
                "throughput": "high",
                "implementation_complexity": "medium",
            },
        },
        {
            "strategy_id": "deterministic_rules_then_review",
            "strengths": {
                "precision": 0.87,
                "recall": 0.58,
                "throughput": 0.83,
                "cost": 0.81,
                "explainability": 0.93,
                "edge_control": 0.89,
                "noise_tolerance": 0.42,
            },
            "expected_tradeoffs": {
                "precision": "high",
                "recall": "medium_low",
                "throughput": "high",
                "implementation_complexity": "low_medium",
            },
        },
    ]
    if allow_embedding_models:
        catalog.append(
            {
                "strategy_id": "embedding_first_nearest_neighbor",
                "strengths": {
                    "precision": 0.73,
                    "recall": 0.9,
                    "throughput": 0.57,
                    "cost": 0.46,
                    "explainability": 0.52,
                    "edge_control": 0.62,
                    "noise_tolerance": 0.93,
                },
                "expected_tradeoffs": {
                    "precision": "medium_high",
                    "recall": "high",
                    "throughput": "medium",
                    "implementation_complexity": "medium_high",
                },
            }
        )
    if allow_graph_clustering:
        catalog.append(
            {
                "strategy_id": "graph_first_collective_resolution",
                "strengths": {
                    "precision": 0.81,
                    "recall": 0.86,
                    "throughput": 0.5,
                    "cost": 0.48,
                    "explainability": 0.59,
                    "edge_control": 0.5,
                    "noise_tolerance": 0.76,
                },
                "expected_tradeoffs": {
                    "precision": "high",
                    "recall": "high",
                    "throughput": "medium_low",
                    "implementation_complexity": "high",
                },
            }
        )
    return catalog


def _objective_target_weights(priority: str) -> Dict[str, float]:
    weights_by_priority: Dict[str, Dict[str, float]] = {
        "balanced": {"precision": 0.24, "recall": 0.2, "throughput": 0.18, "cost": 0.14, "explainability": 0.14, "edge_control": 0.1},
        "precision_first": {"precision": 0.4, "recall": 0.16, "throughput": 0.12, "cost": 0.1, "explainability": 0.12, "edge_control": 0.1},
        "recall_first": {"precision": 0.14, "recall": 0.4, "throughput": 0.12, "cost": 0.08, "explainability": 0.1, "edge_control": 0.16},
        "throughput_first": {"precision": 0.14, "recall": 0.14, "throughput": 0.36, "cost": 0.16, "explainability": 0.06, "edge_control": 0.14},
        "cost_first": {"precision": 0.14, "recall": 0.12, "throughput": 0.18, "cost": 0.34, "explainability": 0.08, "edge_control": 0.14},
        "explainability_first": {"precision": 0.2, "recall": 0.12, "throughput": 0.12, "cost": 0.1, "explainability": 0.32, "edge_control": 0.14},
    }
    return weights_by_priority.get(priority, weights_by_priority["balanced"])


def _signal_adjustment(
    *,
    strategy_id: str,
    strengths: Dict[str, float],
    near_dup_rate: float,
    hub_risk: float,
    avg_entropy: float,
    avg_null: float,
    row_count: int,
) -> float:
    adjustment = 0.0
    if near_dup_rate >= 0.08:
        adjustment += 0.06 * strengths.get("edge_control", 0.0)
    if hub_risk >= 0.2:
        adjustment += 0.08 * strengths.get("edge_control", 0.0)
        if strategy_id == "graph_first_collective_resolution":
            adjustment -= 0.03
    if avg_entropy < 0.45:
        adjustment += 0.05 * strengths.get("noise_tolerance", 0.0)
    else:
        adjustment += 0.03 * strengths.get("precision", 0.0)
    if avg_null > 0.35:
        adjustment -= 0.06 * strengths.get("precision", 0.0)
        adjustment -= 0.04 * strengths.get("throughput", 0.0)
    if row_count >= 500_000:
        adjustment += 0.05 * strengths.get("throughput", 0.0)
    return adjustment


def _constraint_adjustment(*, strengths: Dict[str, float], objective: Dict[str, Any], row_count: int) -> float:
    adjustment = 0.0
    latency_budget_ms = objective.get("latency_budget_ms")
    if isinstance(latency_budget_ms, (int, float)):
        if latency_budget_ms <= 100:
            adjustment += 0.08 * (strengths.get("throughput", 0.0) - 0.6)
        elif latency_budget_ms <= 250:
            adjustment += 0.04 * (strengths.get("throughput", 0.0) - 0.55)

    max_edge_count = objective.get("max_edge_count")
    if isinstance(max_edge_count, int) and row_count > 0:
        edge_budget_ratio = max_edge_count / max(1, row_count)
        if edge_budget_ratio < 1.0:
            adjustment += 0.1 * (strengths.get("edge_control", 0.0) - 0.5)
        elif edge_budget_ratio < 3.0:
            adjustment += 0.05 * (strengths.get("edge_control", 0.0) - 0.45)

    max_candidate_pairs = objective.get("max_candidate_pairs")
    if isinstance(max_candidate_pairs, int) and row_count > 0:
        nominal_pair_space = row_count * row_count
        if nominal_pair_space > 0:
            pair_budget_ratio = max_candidate_pairs / nominal_pair_space
            if pair_budget_ratio < 0.005:
                adjustment += 0.08 * (strengths.get("edge_control", 0.0) - 0.5)
    return adjustment


def _build_strategy_rationale(
    *,
    strategy_id: str,
    objective_priority: str,
    near_dup_rate: float,
    hub_risk: float,
    avg_entropy: float,
) -> List[str]:
    rationale: List[str] = []
    if near_dup_rate >= 0.08:
        rationale.append("Elevated duplicate-rate signal favors stronger candidate pruning")
    if hub_risk >= 0.2:
        rationale.append("Hub-risk signal indicates graph growth controls are important")
    if avg_entropy < 0.45:
        rationale.append("Lower field entropy suggests tolerance for noisy text is beneficial")

    priority_reason = {
        "precision_first": "Objective prioritizes precision over maximal recall",
        "recall_first": "Objective prioritizes recall coverage for difficult matches",
        "throughput_first": "Objective prioritizes throughput and predictable runtime",
        "cost_first": "Objective prioritizes lower operational cost",
        "explainability_first": "Objective prioritizes interpretable matching decisions",
    }.get(objective_priority, "Objective favors balanced precision, recall, and throughput")
    rationale.append(priority_reason)

    strategy_note = {
        "hybrid_block_then_weighted_match": "Hybrid blocking plus weighted matching balances quality and scale",
        "pre_ingest_canonicalize_then_match": "Canonicalization before matching reduces duplicate variants early",
        "deterministic_rules_then_review": "Deterministic rules keep behavior explainable and auditable",
        "embedding_first_nearest_neighbor": "Embedding-first retrieval improves semantic recall on noisy fields",
        "graph_first_collective_resolution": "Collective graph reasoning improves multi-hop consistency",
    }.get(strategy_id)
    if strategy_note:
        rationale.append(strategy_note)

    return rationale[:3]


def _recommendation_confidence(
    *,
    fit_score: float,
    score_gap: float,
    sample_size: int,
    has_pairwise: bool,
    string_field_count: int,
    objective_has_constraints: bool,
) -> Dict[str, Any]:
    score = 0.5
    factors: List[str] = []

    if sample_size >= 1000:
        score += 0.14
        factors.append("sample_size_sufficient")
    elif sample_size > 0:
        score += 0.05
        factors.append("sample_size_limited")
    else:
        factors.append("sample_size_unknown")

    if has_pairwise:
        score += 0.1
        factors.append("pairwise_signals_present")
    else:
        factors.append("pairwise_signals_missing")

    if string_field_count >= 2:
        score += 0.08
        factors.append("field_coverage_sufficient")
    else:
        factors.append("field_coverage_limited")

    if objective_has_constraints:
        score += 0.06
        factors.append("objective_constraints_provided")

    if fit_score >= 0.82:
        score += 0.06
        factors.append("high_fit_score")
    if score_gap >= 0.05:
        score += 0.05
        factors.append("clear_margin_to_next_option")

    return {"score": round(max(0.0, min(1.0, score)), 4), "factors": factors}


def _extract_labeled_rows(feature_matrix_ref: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_rows = feature_matrix_ref.get("rows") or feature_matrix_ref.get("samples") or []
    parsed: List[Dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        label = raw.get("label")
        if label is None:
            label = raw.get("is_match")
        if label is None:
            continue
        if isinstance(label, bool):
            label_int = 1 if label else 0
        else:
            try:
                label_int = int(label)
            except Exception:
                continue
        if label_int not in (0, 1):
            continue

        features_raw = raw.get("features")
        feature_values: Dict[str, float] = {}
        if isinstance(features_raw, dict):
            items = features_raw.items()
        else:
            # Allow flat rows with top-level numeric features.
            items = [
                (k, v)
                for k, v in raw.items()
                if k not in {"label", "is_match", "pair_id", "left_id", "right_id", "features"}
            ]
        for name, value in items:
            try:
                feature_values[str(name)] = float(value)
            except Exception:
                continue
        if not feature_values:
            continue
        parsed.append({"label": label_int, "features": feature_values})
    return parsed


def _feature_separation_score(pos_vals: List[float], neg_vals: List[float]) -> float:
    pos_mean = _mean(pos_vals)
    neg_mean = _mean(neg_vals)
    pooled_std = max(1e-6, _std(pos_vals + neg_vals))
    return abs(pos_mean - neg_mean) / pooled_std


def _normalize_weights(raw_scores: Dict[str, float]) -> Dict[str, float]:
    total = sum(raw_scores.values())
    if total <= 0:
        eq = 1.0 / max(1, len(raw_scores))
        return {k: round(eq, 4) for k in sorted(raw_scores.keys())}
    normalized = {k: v / total for k, v in raw_scores.items()}
    ordered_keys = sorted(normalized.keys())
    rounded = {k: round(normalized[k], 4) for k in ordered_keys}
    # Rebalance rounding remainder onto top-weighted key for stable sum ~= 1.
    remainder = round(1.0 - sum(rounded.values()), 4)
    if ordered_keys:
        top_key = max(ordered_keys, key=lambda k: normalized[k])
        rounded[top_key] = round(max(0.0, rounded[top_key] + remainder), 4)
    return rounded


def _weighted_score(row: Dict[str, Any], weights: Dict[str, float]) -> float:
    features = row.get("features") or {}
    return sum(float(weights.get(name, 0.0)) * float(features.get(name, 0.0)) for name in weights.keys())


def _recommend_match_threshold(
    rows: List[Dict[str, Any]],
    weights: Dict[str, float],
    *,
    target_metric: str,
) -> float:
    pos_scores = sorted(_weighted_score(r, weights) for r in rows if r["label"] == 1)
    neg_scores = sorted(_weighted_score(r, weights) for r in rows if r["label"] == 0)
    if not pos_scores or not neg_scores:
        return 0.8

    if target_metric == "precision_at_recall":
        # Keep roughly 90% recall on positives.
        threshold = _quantile(pos_scores, 0.10)
    elif target_metric == "recall_at_precision":
        # Keep roughly 90% precision by staying above most negatives.
        threshold = _quantile(neg_scores, 0.90)
    else:
        threshold = 0.5 * (_mean(pos_scores) + _mean(neg_scores))
    return max(0.0, min(1.0, threshold))


def _estimate_target_metric(
    rows: List[Dict[str, Any]],
    weights: Dict[str, float],
    threshold: float,
    *,
    target_metric: str,
) -> float:
    tp = fp = fn = 0
    for row in rows:
        predicted_match = _weighted_score(row, weights) >= threshold
        if predicted_match and row["label"] == 1:
            tp += 1
        elif predicted_match and row["label"] == 0:
            fp += 1
        elif (not predicted_match) and row["label"] == 1:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if target_metric == "precision_at_recall":
        return precision
    if target_metric == "recall_at_precision":
        return recall
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _weights_confidence(
    *,
    sample_size: int,
    positive_count: int,
    feature_count: int,
    metric_estimate: float,
) -> Dict[str, Any]:
    score = 0.45
    factors: List[str] = []
    if sample_size >= 5000:
        score += 0.2
        factors.append("sample_size_good")
    elif sample_size >= 1000:
        score += 0.12
        factors.append("sample_size_adequate")
    else:
        factors.append("sample_size_limited")

    class_ratio = positive_count / sample_size if sample_size else 0.0
    if 0.2 <= class_ratio <= 0.8:
        score += 0.1
        factors.append("class_balance_reasonable")
    else:
        factors.append("class_imbalance_detected")

    if feature_count >= 3:
        score += 0.08
        factors.append("feature_coverage_good")
    else:
        factors.append("feature_coverage_limited")

    if metric_estimate >= 0.8:
        score += 0.08
        factors.append("discrimination_signal_strong")
    elif metric_estimate >= 0.65:
        score += 0.04
        factors.append("discrimination_signal_moderate")
    else:
        factors.append("discrimination_signal_weak")

    return {"score": round(max(0.0, min(1.0, score)), 4), "factors": factors}


def _mean(values: List[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    variance = sum((v - mu) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _quantile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    q = max(0.0, min(1.0, q))
    idx = int(round((len(sorted_values) - 1) * q))
    return sorted_values[idx]


def _estimate_variant_metrics(config: Dict[str, Any]) -> Dict[str, float]:
    blocking = config.get("blocking") if isinstance(config.get("blocking"), dict) else {}
    matching = config.get("matching") if isinstance(config.get("matching"), dict) else {}
    embedding = config.get("embedding") if isinstance(config.get("embedding"), dict) else {}
    graph = config.get("graph") if isinstance(config.get("graph"), dict) else {}

    blocking_fields = blocking.get("fields") if isinstance(blocking.get("fields"), list) else []
    field_count = max(1, len(blocking_fields))
    max_block_size = int(blocking.get("max_block_size", 150) or 150)
    max_block_size = max(2, min(5000, max_block_size))
    threshold = float(matching.get("threshold", 0.82) or 0.82)
    threshold = max(0.5, min(0.99, threshold))

    embedding_enabled = bool(embedding.get("enabled", config.get("embedding_enabled", False)))
    graph_enabled = bool(graph.get("enabled", config.get("graph_clustering_enabled", False)))

    pruning_factor = min(1.0, 160.0 / max_block_size)
    estimated_runtime_sec = 90.0 + 42.0 * pruning_factor + 9.0 * field_count
    if embedding_enabled:
        estimated_runtime_sec += 38.0
    if graph_enabled:
        estimated_runtime_sec += 22.0

    estimated_peak_memory_mb = 520.0 + 120.0 * field_count + 1.3 * max_block_size
    if embedding_enabled:
        estimated_peak_memory_mb += 340.0
    if graph_enabled:
        estimated_peak_memory_mb += 260.0

    estimated_storage_mb = 260.0 + 35.0 * field_count + 0.35 * max_block_size
    if graph_enabled:
        estimated_storage_mb += 190.0
    if embedding_enabled:
        estimated_storage_mb += 55.0

    estimated_precision = 0.7 + (threshold - 0.7) * 0.62 + (0.015 * min(3, field_count))
    if graph_enabled:
        estimated_precision += 0.02
    if embedding_enabled:
        estimated_precision -= 0.01

    estimated_recall = 0.62 + (0.9 - threshold) * 0.55 - (0.01 * max(0, field_count - 2))
    if embedding_enabled:
        estimated_recall += 0.09
    if graph_enabled:
        estimated_recall += 0.07

    return {
        "estimated_runtime_sec": round(max(10.0, estimated_runtime_sec), 3),
        "estimated_peak_memory_mb": round(max(64.0, estimated_peak_memory_mb), 3),
        "estimated_precision": round(_clamp(estimated_precision, 0.0, 0.99), 4),
        "estimated_recall": round(_clamp(estimated_recall, 0.0, 0.99), 4),
        "estimated_storage_mb": round(max(20.0, estimated_storage_mb), 3),
    }


def _variant_fit_score(
    *,
    metrics: Dict[str, float],
    objective: Dict[str, Any],
    objective_weights: Dict[str, float],
) -> float:
    throughput_score = _clamp(1.2 - (metrics["estimated_runtime_sec"] / 220.0), 0.0, 1.0)
    cost_score = _clamp(1.2 - ((metrics["estimated_peak_memory_mb"] + metrics["estimated_storage_mb"]) / 2600.0), 0.0, 1.0)
    explainability_score = _clamp(0.88 - (metrics["estimated_runtime_sec"] / 550.0), 0.0, 1.0)
    edge_control_score = _clamp(1.1 - (metrics["estimated_storage_mb"] / 900.0), 0.0, 1.0)

    base_score = (
        objective_weights.get("precision", 0.0) * metrics["estimated_precision"]
        + objective_weights.get("recall", 0.0) * metrics["estimated_recall"]
        + objective_weights.get("throughput", 0.0) * throughput_score
        + objective_weights.get("cost", 0.0) * cost_score
        + objective_weights.get("explainability", 0.0) * explainability_score
        + objective_weights.get("edge_control", 0.0) * edge_control_score
    )

    penalty = 0.0
    max_memory = objective.get("max_memory_mb")
    if isinstance(max_memory, (int, float)) and metrics["estimated_peak_memory_mb"] > float(max_memory):
        over_ratio = (metrics["estimated_peak_memory_mb"] - float(max_memory)) / max(float(max_memory), 1.0)
        penalty += min(0.2, 0.12 * over_ratio)

    latency_budget = objective.get("latency_budget_ms")
    if isinstance(latency_budget, (int, float)):
        # Approximate latency proxy from runtime estimate.
        estimated_latency_ms = max(20.0, metrics["estimated_runtime_sec"] * 1.6)
        if estimated_latency_ms > float(latency_budget):
            over_ratio = (estimated_latency_ms - float(latency_budget)) / max(float(latency_budget), 1.0)
            penalty += min(0.2, 0.1 * over_ratio)

    return _clamp(base_score - penalty, 0.0, 1.0)


def _winner_reason(*, metrics: Dict[str, float], objective: Dict[str, Any], priority: str) -> str:
    if priority == "throughput_first":
        return "Best throughput-oriented fit under objective constraints"
    if priority == "precision_first":
        return "Highest precision-weighted fit while remaining within resource targets"
    if priority == "recall_first":
        return "Highest recall-weighted fit with acceptable runtime and memory"
    if priority == "cost_first":
        return "Best cost-weighted fit with lower projected memory and storage"
    if priority == "explainability_first":
        return "Best explainability-weighted fit with stable projected quality"

    if "max_memory_mb" in objective and metrics["estimated_peak_memory_mb"] <= float(objective["max_memory_mb"]):
        return "Best balanced fit while staying within memory constraints"
    return "Best objective fit across quality, throughput, and resource tradeoffs"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _build_export_config(*, recommendation: Dict[str, Any], include_rationale: bool) -> Dict[str, Any]:
    strategy_id = recommendation.get("strategy_id", "hybrid_block_then_weighted_match")
    blocking = recommendation.get("blocking") if isinstance(recommendation.get("blocking"), dict) else {}
    matching = recommendation.get("matching") if isinstance(recommendation.get("matching"), dict) else {}

    payload: Dict[str, Any] = {
        "entity_resolution": {
            "strategy": strategy_id,
            "blocking": {
                "fields": blocking.get("fields", []),
                "max_block_size": int(blocking.get("max_block_size", 100) or 100),
                "min_block_size": int(blocking.get("min_block_size", 2) or 2),
            },
            "matching": {
                "threshold": float(matching.get("threshold", 0.82) or 0.82),
                "weights": matching.get("weights", recommendation.get("weights", {})),
            },
            "metadata": {
                "advisor_policy_version": ADVISOR_POLICY_VERSION,
            },
        }
    }

    if include_rationale:
        payload["entity_resolution"]["metadata"]["rationale"] = recommendation.get("rationale", [])
        payload["entity_resolution"]["metadata"]["fit_score"] = recommendation.get("fit_score")
        if isinstance(recommendation.get("expected_tradeoffs"), dict):
            payload["entity_resolution"]["metadata"]["expected_tradeoffs"] = recommendation["expected_tradeoffs"]

    return payload
