"""
Pipeline-level MCP tools: find_duplicates and pipeline_status.
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

from arango import ArangoClient
from entity_resolution.mcp.contracts import FindDuplicatesRequest
from entity_resolution.mcp.connection import get_arango_hosts
from entity_resolution.utils.pipeline_utils import count_inferred_edges, validate_edge_quality

ER_OPTIONS_SCHEMA_VERSION = "1.0"


def _get_db(host: str, port: int, username: str, password: str, database: str):
    """Return an authenticated ArangoDB database handle."""
    client = ArangoClient(hosts=get_arango_hosts(host, port))
    return client.db(database, username=username, password=password)


def run_find_duplicates(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection: str,
    strategy: str = "exact",
    fields: list[str] | None = None,
    confidence_threshold: float = 0.85,
    max_block_size: int = 500,
    store_clusters: bool = True,
    edge_collection: str | None = None,
    enable_active_learning: bool = False,
    feedback_collection: str | None = None,
    active_learning_refresh_every: int = 100,
    active_learning_model: str | None = None,
    active_learning_low_threshold: float = 0.55,
    active_learning_high_threshold: float = 0.80,
) -> Dict[str, Any]:
    """
    Run the full blocking → similarity → edge-creation → clustering pipeline
    on *collection* and return a metrics summary.
    """
    request = FindDuplicatesRequest(
        collection=collection,
        fields=fields or [],
        strategy=strategy,
        confidence_threshold=confidence_threshold,
        max_block_size=max_block_size,
        store_clusters=store_clusters,
        edge_collection=edge_collection,
        enable_active_learning=enable_active_learning,
        feedback_collection=feedback_collection,
        active_learning_refresh_every=active_learning_refresh_every,
        active_learning_model=active_learning_model,
        active_learning_low_threshold=active_learning_low_threshold,
        active_learning_high_threshold=active_learning_high_threshold,
    )
    return run_find_duplicates_request(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        request=request,
    )


def run_find_duplicates_request(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    request: FindDuplicatesRequest,
) -> Dict[str, Any]:
    """
    Run find_duplicates using a canonical normalized request object.

    Preferred internal entrypoint for MCP wrappers after normalization.
    """
    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    db = _get_db(host, port, username, password, database)
    edge_coll = request.edge_collection or f"{request.collection}_similarity_edges"

    if not request.stages:
        if _has_precision_gates(request):
            return _run_single_stage_with_optional_gating(
                db=db,
                request=request,
                edge_collection=edge_coll,
                strategy=request.strategy,
                fields=request.fields or [],
                threshold=request.confidence_threshold,
                store_clusters=request.store_clusters,
                stage_meta=None,
            )
        cfg = _build_pipeline_config(
            request=request,
            edge_collection=edge_coll,
            strategy=request.strategy,
            fields=request.fields or [],
            threshold=request.confidence_threshold,
            store_clusters=request.store_clusters,
        )
        pipeline = ConfigurableERPipeline(db=db, config=cfg)
        return _with_schema_version(pipeline.run())

    if len(request.stages) == 1:
        stage_strategy, stage_fields, stage_threshold, stage_meta = _resolve_stage_scaffold(request)
        if _has_precision_gates(request):
            return _run_single_stage_with_optional_gating(
                db=db,
                request=request,
                edge_collection=edge_coll,
                strategy=stage_strategy,
                fields=stage_fields,
                threshold=stage_threshold,
                store_clusters=request.store_clusters,
                stage_meta=stage_meta,
            )
        cfg = _build_pipeline_config(
            request=request,
            edge_collection=edge_coll,
            strategy=stage_strategy,
            fields=stage_fields,
            threshold=stage_threshold,
            store_clusters=request.store_clusters,
        )
        pipeline = ConfigurableERPipeline(db=db, config=cfg)
        results = pipeline.run()
        results["stages"] = stage_meta
        return _with_schema_version(results)

    # C2: true staged execution for >=2 stages with unresolved escalation.
    return _run_find_duplicates_multistage(
        db=db,
        request=request,
        edge_collection=edge_coll,
    )


def _resolve_stage_scaffold(request: FindDuplicatesRequest) -> Tuple[str, list[str], float, Dict[str, Any]]:
    """
    C2 scaffold: map first stage into current single-pass pipeline knobs.

    This preserves current pipeline behavior while exposing `options.stages`
    shape in request/response contracts. Full multi-pass execution will follow
    in the next C2 increment.
    """
    strategy = request.strategy
    fields = request.fields or []
    threshold = request.confidence_threshold
    if not request.stages:
        return strategy, fields, threshold, {}

    stages = request.stages
    first = stages[0]
    stage_type = str(first.get("type", "")).lower()
    stage_fields = first.get("fields")
    min_score = first.get("min_score")

    if isinstance(stage_fields, list) and stage_fields:
        fields = [str(f) for f in stage_fields]
    if isinstance(min_score, (int, float)):
        threshold = float(min_score)
    if stage_type in {"exact", "blocking_exact"}:
        strategy = "exact"
    elif stage_type in {"bm25", "arangosearch"}:
        strategy = "bm25"
    elif stage_type in {"embedding", "vector"}:
        strategy = "vector"

    meta = {
        "enabled": True,
        "requested_stage_count": len(stages),
        "execution_mode": "single_stage_scaffold",
        "selected_stage_index": 0,
        "selected_stage_type": stage_type or "unspecified",
        "selected_stage_fields": fields,
        "selected_stage_min_score": threshold,
    }
    return strategy, fields, threshold, meta


def _build_pipeline_config(
    *,
    request: FindDuplicatesRequest,
    edge_collection: str,
    strategy: str,
    fields: list[str],
    threshold: float,
    store_clusters: bool,
):
    from entity_resolution.config.er_config import (
        ActiveLearningConfig,
        BlockingConfig,
        ClusteringConfig,
        ERPipelineConfig,
        SimilarityConfig,
    )

    return ERPipelineConfig(
        entity_type="generic",
        collection_name=request.collection,
        edge_collection=edge_collection,
        cluster_collection=f"{request.collection}_clusters",
        blocking=BlockingConfig(
            strategy=strategy,
            fields=_augment_blocking_fields_with_alias_sources(fields, request),
            max_block_size=request.max_block_size,
        ),
        similarity=SimilarityConfig(
            threshold=threshold,
        ),
        clustering=ClusteringConfig(
            store_results=store_clusters,
        ),
        active_learning=ActiveLearningConfig(
            enabled=request.enable_active_learning,
            feedback_collection=request.feedback_collection,
            refresh_every=request.active_learning_refresh_every,
            model=request.active_learning_model,
            low_threshold=request.active_learning_low_threshold,
            high_threshold=request.active_learning_high_threshold,
        ),
    )


def _run_find_duplicates_multistage(*, db: Any, request: FindDuplicatesRequest, edge_collection: str) -> Dict[str, Any]:
    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    started = time.time()
    alias_profile = _build_aliasing_profile(request)
    stage_results: list[Dict[str, Any]] = []
    total_candidates = 0
    total_matches = 0
    total_edges = 0

    for idx, stage in enumerate(request.stages):
        stage_start = time.time()
        strategy, fields, threshold = _resolve_stage_config(stage, request)
        cfg = _build_pipeline_config(
            request=request,
            edge_collection=edge_collection,
            strategy=strategy,
            fields=fields,
            threshold=threshold,
            store_clusters=False,
        )
        pipeline = ConfigurableERPipeline(db=db, config=cfg)

        unresolved_ids = _get_unresolved_doc_ids(db, request.collection, edge_collection)
        candidate_pairs = pipeline.run_blocking()
        filtered_pairs = _filter_candidate_pairs_by_doc_ids(
            candidate_pairs=candidate_pairs,
            unresolved_ids=unresolved_ids,
            collection=request.collection,
        )
        matches = pipeline.run_similarity(filtered_pairs) if filtered_pairs else []
        accepted_matches, gate_stats = _apply_precision_gates(
            db=db,
            collection=request.collection,
            matches=matches,
            fields=fields or request.fields or [],
            request=request,
        )
        edges_created = pipeline.run_edge_creation(accepted_matches) if accepted_matches else 0

        total_candidates += len(filtered_pairs)
        total_matches += len(accepted_matches)
        total_edges += int(edges_created)
        stage_results.append(
            {
                "stage_index": idx,
                "stage_type": str(stage.get("type", "unspecified")),
                "strategy": strategy,
                "fields": fields,
                "threshold": threshold,
                "unresolved_before": len(unresolved_ids),
                "candidate_pairs": len(filtered_pairs),
                "matches_found": len(accepted_matches),
                "edges_created": int(edges_created),
                "gates": gate_stats,
                "runtime_seconds": round(time.time() - stage_start, 3),
            }
        )

    clustering_runtime = 0.0
    clusters_found = 0
    if request.store_clusters and _has_any_edges(db, edge_collection):
        cluster_start = time.time()
        # Reuse pipeline clustering implementation with final-stage config.
        final_strategy, final_fields, final_threshold = _resolve_stage_config(request.stages[-1], request)
        cfg = _build_pipeline_config(
            request=request,
            edge_collection=edge_collection,
            strategy=final_strategy,
            fields=final_fields,
            threshold=final_threshold,
            store_clusters=True,
        )
        pipeline = ConfigurableERPipeline(db=db, config=cfg)
        clusters = pipeline.run_clustering()
        clustering_runtime = round(time.time() - cluster_start, 3)
        clusters_found = len(clusters)

    total_runtime = round(time.time() - started, 3)
    return _with_schema_version({
        "embedding": {},
        "blocking": {
            "candidate_pairs": total_candidates,
            "runtime_seconds": round(sum(s["runtime_seconds"] for s in stage_results), 3),
        },
        "similarity": {
            "matches_found": total_matches,
            "pairs_processed": total_candidates,
            "runtime_seconds": round(sum(s["runtime_seconds"] for s in stage_results), 3),
            "active_learning": {
                "enabled": bool(request.enable_active_learning),
                "pairs_reviewed": 0,
                "llm_calls": 0,
                "score_overrides": 0,
                "feedback_collection": request.feedback_collection,
            },
        },
        "edges": {
            "edges_created": total_edges,
            "runtime_seconds": round(sum(s["runtime_seconds"] for s in stage_results), 3),
        },
        "clustering": {
            "clusters_found": clusters_found,
            "runtime_seconds": clustering_runtime,
        },
        "total_runtime_seconds": total_runtime,
        "stages": {
            "enabled": True,
            "requested_stage_count": len(request.stages),
            "execution_mode": "multi_stage",
            "stage_results": stage_results,
            "gating": {
                "enabled": _has_precision_gates(request),
                "mode": request.gating_mode,
                "aliasing": {
                    "configured": bool(alias_profile.get("inline_map") or alias_profile.get("field_sources") or alias_profile.get("acronym_auto")),
                    "managed_ref_requested": alias_profile.get("managed_ref_requested", []),
                    "managed_ref_applied": alias_profile.get("managed_ref_applied", []),
                    "managed_ref_missing": alias_profile.get("managed_ref_missing", []),
                },
                "similarity_type": request.similarity_type,
                "token_jaccard_fields": request.token_jaccard_fields,
                "token_jaccard_min_score": request.token_jaccard_min_score,
                "min_margin": request.min_margin,
                "require_token_overlap": request.require_token_overlap,
                "token_overlap_bypass_score": request.token_overlap_bypass_score,
                "target_type_field": request.target_type_field,
            },
        },
    })


def _run_single_stage_with_optional_gating(
    *,
    db: Any,
    request: FindDuplicatesRequest,
    edge_collection: str,
    strategy: str,
    fields: list[str],
    threshold: float,
    store_clusters: bool,
    stage_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    started = time.time()
    cfg = _build_pipeline_config(
        request=request,
        edge_collection=edge_collection,
        strategy=strategy,
        fields=fields,
        threshold=threshold,
        store_clusters=False,
    )
    pipeline = ConfigurableERPipeline(db=db, config=cfg)
    candidate_pairs = pipeline.run_blocking()
    matches = pipeline.run_similarity(candidate_pairs) if candidate_pairs else []
    accepted_matches, gate_stats = _apply_precision_gates(
        db=db,
        collection=request.collection,
        matches=matches,
        fields=fields,
        request=request,
    )
    edges_created = pipeline.run_edge_creation(accepted_matches) if accepted_matches else 0

    clusters_found = 0
    clustering_runtime = 0.0
    if store_clusters and _has_any_edges(db, edge_collection):
        cluster_start = time.time()
        cfg_cluster = _build_pipeline_config(
            request=request,
            edge_collection=edge_collection,
            strategy=strategy,
            fields=fields,
            threshold=threshold,
            store_clusters=True,
        )
        cluster_pipeline = ConfigurableERPipeline(db=db, config=cfg_cluster)
        clusters = cluster_pipeline.run_clustering()
        clusters_found = len(clusters)
        clustering_runtime = round(time.time() - cluster_start, 3)

    runtime = round(time.time() - started, 3)
    result: Dict[str, Any] = {
        "embedding": {},
        "blocking": {"candidate_pairs": len(candidate_pairs), "runtime_seconds": runtime},
        "similarity": {
            "matches_found": len(accepted_matches),
            "pairs_processed": len(candidate_pairs),
            "runtime_seconds": runtime,
            "active_learning": {
                "enabled": bool(request.enable_active_learning),
                "pairs_reviewed": 0,
                "llm_calls": 0,
                "score_overrides": 0,
                "feedback_collection": request.feedback_collection,
            },
            "gates": gate_stats,
        },
        "edges": {"edges_created": int(edges_created), "runtime_seconds": runtime},
        "clustering": {"clusters_found": clusters_found, "runtime_seconds": clustering_runtime},
        "total_runtime_seconds": runtime,
    }
    if stage_meta:
        alias_profile = _build_aliasing_profile(request)
        meta = dict(stage_meta)
        meta["gating"] = {
            "enabled": _has_precision_gates(request),
            "mode": request.gating_mode,
            "aliasing": {
                "configured": bool(alias_profile.get("inline_map") or alias_profile.get("field_sources") or alias_profile.get("acronym_auto")),
                "managed_ref_requested": alias_profile.get("managed_ref_requested", []),
                "managed_ref_applied": alias_profile.get("managed_ref_applied", []),
                "managed_ref_missing": alias_profile.get("managed_ref_missing", []),
            },
            "similarity_type": request.similarity_type,
            "token_jaccard_fields": request.token_jaccard_fields,
            "token_jaccard_min_score": request.token_jaccard_min_score,
            "min_margin": request.min_margin,
            "require_token_overlap": request.require_token_overlap,
            "token_overlap_bypass_score": request.token_overlap_bypass_score,
            "target_type_field": request.target_type_field,
        }
        result["stages"] = meta
    return _with_schema_version(result)


def _resolve_stage_config(stage: Dict[str, Any], request: FindDuplicatesRequest) -> Tuple[str, list[str], float]:
    strategy = request.strategy
    fields = request.fields or []
    threshold = request.confidence_threshold

    stage_type = str(stage.get("type", "")).lower()
    if stage_type in {"exact", "blocking_exact"}:
        strategy = "exact"
    elif stage_type in {"bm25", "arangosearch"}:
        strategy = "bm25"
    elif stage_type in {"embedding", "vector"}:
        strategy = "vector"

    stage_fields = stage.get("fields")
    if isinstance(stage_fields, list) and stage_fields:
        fields = [str(f) for f in stage_fields]

    if isinstance(stage.get("min_score"), (float, int)):
        threshold = float(stage["min_score"])

    return strategy, fields, threshold


def _get_unresolved_doc_ids(db: Any, collection: str, edge_collection: str) -> set[str]:
    if not db.has_collection(collection):
        return set()
    if not db.has_collection(edge_collection):
        cursor = db.aql.execute("FOR d IN @@collection RETURN d._id", bind_vars={"@collection": collection})
        return {str(doc_id) for doc_id in cursor}

    cursor = db.aql.execute(
        """
        FOR d IN @@collection
          LET linked = LENGTH(
            FOR e IN @@edge_collection
              FILTER e._from == d._id OR e._to == d._id
              LIMIT 1
              RETURN 1
          )
          FILTER linked == 0
          RETURN d._id
        """,
        bind_vars={
            "@collection": collection,
            "@edge_collection": edge_collection,
        },
    )
    return {str(doc_id) for doc_id in cursor}


def _filter_candidate_pairs_by_doc_ids(
    *,
    candidate_pairs: list[Any],
    unresolved_ids: set[str],
    collection: str,
) -> list[Any]:
    if not unresolved_ids:
        return []

    filtered: list[Any] = []
    seen: set[Tuple[str, str]] = set()
    for pair in candidate_pairs:
        doc1_id: Optional[str] = None
        doc2_id: Optional[str] = None
        if isinstance(pair, dict):
            k1 = str(pair.get("doc1_key", ""))
            k2 = str(pair.get("doc2_key", ""))
            doc1_id = k1 if "/" in k1 else f"{collection}/{k1}"
            doc2_id = k2 if "/" in k2 else f"{collection}/{k2}"
        elif isinstance(pair, tuple) and len(pair) >= 2:
            k1 = str(pair[0])
            k2 = str(pair[1])
            doc1_id = k1 if "/" in k1 else f"{collection}/{k1}"
            doc2_id = k2 if "/" in k2 else f"{collection}/{k2}"

        if not doc1_id or not doc2_id:
            continue
        if doc1_id not in unresolved_ids or doc2_id not in unresolved_ids:
            continue

        dedupe_key = tuple(sorted((doc1_id, doc2_id)))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        filtered.append(pair)
    return filtered


def _has_any_edges(db: Any, edge_collection: str) -> bool:
    if not db.has_collection(edge_collection):
        return False
    try:
        return int(db.collection(edge_collection).count()) > 0
    except Exception:
        return False


def _has_precision_gates(request: FindDuplicatesRequest) -> bool:
    return bool(
        request.similarity_type == "token_jaccard"
        or request.token_jaccard_min_score > 0.0
        or request.min_margin > 0.0
        or request.require_token_overlap
        or bool(request.token_type_affinity)
    )


def _apply_precision_gates(
    *,
    db: Any,
    collection: str,
    matches: list[Any],
    fields: list[str],
    request: FindDuplicatesRequest,
) -> Tuple[list[Any], Dict[str, Any]]:
    alias_profile = _build_aliasing_profile(request)
    if not matches:
        return [], {
            "enabled": _has_precision_gates(request),
            "mode": request.gating_mode,
            "enforcement_enabled": request.gating_mode == "enforce",
            "aliasing": {
                "configured": bool(alias_profile.get("inline_map") or alias_profile.get("field_sources") or alias_profile.get("acronym_auto")),
                "managed_ref_requested": alias_profile.get("managed_ref_requested", []),
                "managed_ref_applied": alias_profile.get("managed_ref_applied", []),
                "managed_ref_missing": alias_profile.get("managed_ref_missing", []),
            },
            "input_matches": 0,
            "accepted_matches": 0,
            "rejected_token_jaccard": 0,
            "rejected_margin": 0,
            "rejected_token_overlap": 0,
            "rejected_type_affinity": 0,
            "would_reject_token_jaccard": 0,
            "would_reject_margin": 0,
            "would_reject_token_overlap": 0,
            "would_reject_type_affinity": 0,
        }

    if not _has_precision_gates(request):
        return matches, {
            "enabled": False,
            "mode": request.gating_mode,
            "enforcement_enabled": False,
            "aliasing": {
                "configured": bool(alias_profile.get("inline_map") or alias_profile.get("field_sources") or alias_profile.get("acronym_auto")),
                "managed_ref_requested": alias_profile.get("managed_ref_requested", []),
                "managed_ref_applied": alias_profile.get("managed_ref_applied", []),
                "managed_ref_missing": alias_profile.get("managed_ref_missing", []),
            },
            "input_matches": len(matches),
            "accepted_matches": len(matches),
            "rejected_token_jaccard": 0,
            "rejected_margin": 0,
            "rejected_token_overlap": 0,
            "rejected_type_affinity": 0,
            "would_reject_token_jaccard": 0,
            "would_reject_margin": 0,
            "would_reject_token_overlap": 0,
            "would_reject_type_affinity": 0,
        }

    enforce = request.gating_mode == "enforce"
    would_reject_token_jaccard = 0
    would_reject_margin = 0
    would_reject_overlap = 0
    would_reject_type_affinity = 0
    rejected_token_jaccard = 0
    rejected_margin = 0
    rejected_overlap = 0
    rejected_type_affinity = 0
    accepted: list[Any] = []

    margin_index = _build_margin_index(matches, collection=collection)
    token_index: Dict[str, set[str]] = {}
    jaccard_fields = _merge_unique_fields(request.token_jaccard_fields, fields)
    if request.similarity_type == "token_jaccard" or request.require_token_overlap or request.token_type_affinity:
        token_index = _build_doc_token_index(
            db=db,
            collection=collection,
            matches=matches,
            fields=jaccard_fields,
            stopwords=request.word_index_stopwords,
            alias_profile=alias_profile,
        )
    type_index: Dict[str, str] = {}
    if request.token_type_affinity:
        type_index = _build_doc_type_index(
            db=db,
            collection=collection,
            matches=matches,
            target_type_field=request.target_type_field,
        )
    min_token_jaccard = (
        request.token_jaccard_min_score
        if request.token_jaccard_min_score > 0.0
        else request.confidence_threshold
    )

    for m in matches:
        doc1, doc2, score = _match_parts(m, collection=collection)
        if doc1 is None or doc2 is None:
            continue
        score_f = float(score)

        if request.similarity_type == "token_jaccard":
            t1 = token_index.get(doc1, set())
            t2 = token_index.get(doc2, set())
            token_jaccard = _jaccard_tokens(t1, t2)
            if token_jaccard < min_token_jaccard:
                would_reject_token_jaccard += 1
                if enforce:
                    rejected_token_jaccard += 1
                    continue

        if request.min_margin > 0.0:
            margin_a = score_f - margin_index[doc1][1]
            margin_b = score_f - margin_index[doc2][1]
            if margin_a < request.min_margin or margin_b < request.min_margin:
                would_reject_margin += 1
                if enforce:
                    rejected_margin += 1
                    continue

        if request.require_token_overlap and score_f < request.token_overlap_bypass_score:
            t1 = token_index.get(doc1, set())
            t2 = token_index.get(doc2, set())
            if not (t1 & t2):
                would_reject_overlap += 1
                if enforce:
                    rejected_overlap += 1
                    continue

        if request.token_type_affinity:
            source_tokens = token_index.get(doc1, set())
            candidate_type = type_index.get(doc2, "")
            if candidate_type:
                if _reject_by_type_affinity(
                    source_tokens=source_tokens,
                    candidate_type=candidate_type,
                    affinity=request.token_type_affinity,
                ):
                    would_reject_type_affinity += 1
                    if enforce:
                        rejected_type_affinity += 1
                        continue

        accepted.append(m)

    return accepted, {
        "enabled": True,
        "mode": request.gating_mode,
        "enforcement_enabled": enforce,
        "aliasing": {
            "configured": bool(alias_profile.get("inline_map") or alias_profile.get("field_sources") or alias_profile.get("acronym_auto")),
            "managed_ref_requested": alias_profile.get("managed_ref_requested", []),
            "managed_ref_applied": alias_profile.get("managed_ref_applied", []),
            "managed_ref_missing": alias_profile.get("managed_ref_missing", []),
        },
        "input_matches": len(matches),
        "accepted_matches": len(accepted),
        "rejected_token_jaccard": rejected_token_jaccard,
        "rejected_margin": rejected_margin,
        "rejected_token_overlap": rejected_overlap,
        "rejected_type_affinity": rejected_type_affinity,
        "would_reject_token_jaccard": would_reject_token_jaccard,
        "would_reject_margin": would_reject_margin,
        "would_reject_token_overlap": would_reject_overlap,
        "would_reject_type_affinity": would_reject_type_affinity,
        "similarity_type": request.similarity_type,
        "token_jaccard_min_score": min_token_jaccard if request.similarity_type == "token_jaccard" else 0.0,
        "token_jaccard_fields": jaccard_fields if request.similarity_type == "token_jaccard" else [],
        "min_margin": request.min_margin,
        "require_token_overlap": request.require_token_overlap,
        "token_overlap_bypass_score": request.token_overlap_bypass_score,
        "target_type_field": request.target_type_field,
    }


def _build_margin_index(matches: list[Any], *, collection: str) -> Dict[str, Tuple[float, float]]:
    scores: Dict[str, list[float]] = defaultdict(list)
    for m in matches:
        doc1, doc2, score = _match_parts(m, collection=collection)
        if doc1 is None or doc2 is None:
            continue
        score_f = float(score)
        scores[doc1].append(score_f)
        scores[doc2].append(score_f)

    idx: Dict[str, Tuple[float, float]] = {}
    for doc_id, vals in scores.items():
        vals_sorted = sorted(vals, reverse=True)
        best = vals_sorted[0] if vals_sorted else 0.0
        second = vals_sorted[1] if len(vals_sorted) > 1 else 0.0
        idx[doc_id] = (best, second)
    return idx


def _build_doc_token_index(
    *,
    db: Any,
    collection: str,
    matches: list[Any],
    fields: list[str],
    stopwords: list[str],
    alias_profile: Dict[str, Any],
) -> Dict[str, set[str]]:
    coll = db.collection(collection)
    doc_ids: set[str] = set()
    for m in matches:
        doc1, doc2, _score = _match_parts(m, collection=collection)
        if doc1:
            doc_ids.add(doc1)
        if doc2:
            doc_ids.add(doc2)

    index: Dict[str, set[str]] = {}
    alias_fields = alias_profile.get("field_sources", [])
    for doc_id in doc_ids:
        key = doc_id.split("/", 1)[1] if "/" in doc_id else doc_id
        doc = coll.get(key) or {}
        tokens: set[str] = set()
        for field in _merge_unique_fields(fields, alias_fields):
            val = doc.get(field)
            if val is None:
                continue
            if isinstance(val, str):
                tokens |= _tokenize_text(
                    val,
                    stopwords,
                    acronym_auto=alias_profile.get("acronym_auto", False),
                    acronym_min_word_len=alias_profile.get("acronym_min_word_len", 4),
                )
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        tokens |= _tokenize_text(
                            item,
                            stopwords,
                            acronym_auto=alias_profile.get("acronym_auto", False),
                            acronym_min_word_len=alias_profile.get("acronym_min_word_len", 4),
                        )
        tokens = _expand_tokens_with_alias_map(tokens, alias_profile.get("inline_map", {}))
        index[doc_id] = tokens
    return index


def _build_doc_type_index(
    *,
    db: Any,
    collection: str,
    matches: list[Any],
    target_type_field: str,
) -> Dict[str, str]:
    coll = db.collection(collection)
    doc_ids: set[str] = set()
    for m in matches:
        doc1, doc2, _score = _match_parts(m, collection=collection)
        if doc1:
            doc_ids.add(doc1)
        if doc2:
            doc_ids.add(doc2)

    index: Dict[str, str] = {}
    for doc_id in doc_ids:
        key = doc_id.split("/", 1)[1] if "/" in doc_id else doc_id
        doc = coll.get(key) or {}
        val = doc.get(target_type_field)
        if val is None:
            continue
        index[doc_id] = str(val).strip()
    return index


def _tokenize_text(
    value: str,
    stopwords: list[str],
    *,
    acronym_auto: bool = False,
    acronym_min_word_len: int = 4,
) -> set[str]:
    raw = re.findall(r"[A-Za-z0-9]+", value.lower())
    sw = set(stopwords or [])
    tokens = {tok for tok in raw if tok and tok not in sw}
    if acronym_auto:
        words = [tok for tok in raw if tok and len(tok) >= max(1, int(acronym_min_word_len))]
        if len(words) >= 2:
            acronym = "".join(w[0] for w in words)
            if acronym:
                tokens.add(acronym)
    return tokens


def _jaccard_tokens(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return float(len(tokens_a & tokens_b)) / float(len(union))


def _reject_by_type_affinity(
    *,
    source_tokens: set[str],
    candidate_type: str,
    affinity: Dict[str, list[str]],
) -> bool:
    """
    Return True when contextual token->type rules reject this candidate.

    Rule model:
    - If no affinity token is present, do not reject.
    - If one or more affinity tokens are present, candidate_type must satisfy
      at least one corresponding allowed type set.
    """
    ctype = candidate_type.strip()
    if not ctype:
        return False
    matched_sets: list[set[str]] = []
    for token in source_tokens:
        allowed = affinity.get(token)
        if allowed:
            matched_sets.append(set(allowed))
    if not matched_sets:
        return False
    return not any(ctype in allowed for allowed in matched_sets)


def _match_parts(match: Any, *, collection: str) -> Tuple[Optional[str], Optional[str], float]:
    if isinstance(match, tuple) and len(match) >= 3:
        a, b, s = str(match[0]), str(match[1]), float(match[2])
    elif isinstance(match, dict):
        a = str(match.get("doc1_key", ""))
        b = str(match.get("doc2_key", ""))
        s = float(match.get("score", match.get("weighted_score", 0.0)))
    else:
        return None, None, 0.0

    if collection:
        a = a if "/" in a else f"{collection}/{a}"
        b = b if "/" in b else f"{collection}/{b}"
    return a, b, s


def _build_aliasing_profile(request: FindDuplicatesRequest) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "inline_map": {},
        "field_sources": [],
        "acronym_auto": False,
        "acronym_min_word_len": 4,
        "managed_ref_requested": [],
        "managed_ref_applied": [],
        "managed_ref_missing": [],
    }
    for source in request.alias_sources:
        source_type = str(source.get("type", "")).lower()
        if source_type == "inline":
            raw_map = source.get("map", {})
            _merge_alias_map(profile["inline_map"], raw_map)
        elif source_type == "field":
            field = str(source.get("field", "")).strip()
            if field:
                profile["field_sources"].append(field)
        elif source_type == "acronym":
            if bool(source.get("auto", True)):
                profile["acronym_auto"] = True
            profile["acronym_min_word_len"] = int(source.get("min_word_len", 4))
        elif source_type == "managed_ref":
            ref = str(source.get("ref", "")).strip()
            managed = request.options.aliasing.get("managed_refs", {})
            if ref:
                profile["managed_ref_requested"].append(ref)
            if ref and isinstance(managed, dict):
                ref_map = managed.get(ref)
                if isinstance(ref_map, dict):
                    _merge_alias_map(profile["inline_map"], ref_map)
                    profile["managed_ref_applied"].append(ref)
                else:
                    profile["managed_ref_missing"].append(ref)
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
        mapped = inline_map.get(tok, [])
        for m in mapped:
            if m:
                expanded.add(m)
    return expanded


def _merge_alias_map(target: Dict[str, list[str]], value: Any) -> None:
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


def _augment_blocking_fields_with_alias_sources(fields: list[str], request: FindDuplicatesRequest) -> list[str]:
    alias_fields = [
        str(s.get("field", "")).strip()
        for s in request.alias_sources
        if str(s.get("type", "")).lower() == "field"
    ]
    return _merge_unique_fields(fields, alias_fields)


def _merge_unique_fields(primary: list[str], extra: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in list(primary or []) + list(extra or []):
        f = str(raw).strip()
        if not f or f in seen:
            continue
        seen.add(f)
        out.append(f)
    return out


def run_pipeline_status(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection: str,
    edge_collection: str | None = None,
) -> Dict[str, Any]:
    """Return stats about a collection's current ER state."""
    from entity_resolution.utils.pipeline_utils import count_inferred_edges, validate_edge_quality

    db = _get_db(host, port, username, password, database)
    edge_coll = edge_collection or f"{collection}_similarity_edges"

    total_docs = db.collection(collection).count() if db.has_collection(collection) else 0
    has_edges = db.has_collection(edge_coll)

    edge_stats: Dict[str, Any] = {}
    if has_edges:
        try:
            edge_stats = count_inferred_edges(db, edge_collection=edge_coll)
        except Exception as exc:
            edge_stats = {"error": str(exc)}

    cluster_coll = f"{collection}_clusters"
    cluster_count = 0
    if db.has_collection(cluster_coll):
        try:
            cluster_count = db.collection(cluster_coll).count()
        except Exception as e:
            logger.debug("Could not count clusters in %s: %s", cluster_coll, e)

    return _with_schema_version({
        "collection": collection,
        "total_documents": total_docs,
        "edge_collection": edge_coll,
        "edge_stats": edge_stats,
        "cluster_collection": cluster_coll,
        "cluster_count": cluster_count,
    })


def _with_schema_version(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload)
    out.setdefault("er_options_schema_version", ER_OPTIONS_SCHEMA_VERSION)
    return out
