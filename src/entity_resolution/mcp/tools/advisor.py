"""
Advisor-level MCP tools: dataset profiling and blocking recommendations.
"""
from __future__ import annotations

import math
from collections import Counter
from itertools import combinations
from typing import Any, Dict, List, Optional

from arango import ArangoClient

TOOL_VERSION = "1.0.0"
ADVISOR_POLICY_VERSION = "2026-03-01"


def _get_db(host: str, port: int, username: str, password: str, database: str):
    client = ArangoClient(hosts=f"http://{host}:{port}")
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


def _ok(*, result: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
    return {
        "status": "ok",
        "tool_version": TOOL_VERSION,
        "advisor_policy_version": ADVISOR_POLICY_VERSION,
        "request_id": request_id,
        "result": result,
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
