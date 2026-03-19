"""
Pipeline-level MCP tools: find_duplicates and pipeline_status.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from arango import ArangoClient
from entity_resolution.mcp.contracts import FindDuplicatesRequest
from entity_resolution.mcp.connection import get_arango_hosts
from entity_resolution.utils.pipeline_utils import count_inferred_edges, validate_edge_quality


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
    from entity_resolution.config.er_config import (
        BlockingConfig,
        ClusteringConfig,
        ERPipelineConfig,
        SimilarityConfig,
        ActiveLearningConfig,
    )
    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    db = _get_db(host, port, username, password, database)
    edge_coll = request.edge_collection or f"{request.collection}_similarity_edges"

    cfg = ERPipelineConfig(
        entity_type="generic",
        collection_name=request.collection,
        edge_collection=edge_coll,
        cluster_collection=f"{request.collection}_clusters",
        blocking=BlockingConfig(
            strategy=request.strategy,
            fields=request.fields or [],
            max_block_size=request.max_block_size,
        ),
        similarity=SimilarityConfig(
            threshold=request.confidence_threshold,
        ),
        clustering=ClusteringConfig(
            store_results=request.store_clusters,
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

    pipeline = ConfigurableERPipeline(db=db, config=cfg)
    results = pipeline.run()
    return results


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
        except Exception:
            pass

    return {
        "collection": collection,
        "total_documents": total_docs,
        "edge_collection": edge_coll,
        "edge_stats": edge_stats,
        "cluster_collection": cluster_coll,
        "cluster_count": cluster_count,
    }
