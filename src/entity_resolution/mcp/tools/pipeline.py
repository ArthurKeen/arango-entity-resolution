"""
Pipeline-level MCP tools: find_duplicates and pipeline_status.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from arango import ArangoClient
from entity_resolution.utils.pipeline_utils import count_inferred_edges, validate_edge_quality


def _get_db(host: str, port: int, username: str, password: str, database: str):
    """Return an authenticated ArangoDB database handle."""
    client = ArangoClient(hosts=f"http://{host}:{port}")
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
) -> Dict[str, Any]:
    """
    Run the full blocking → similarity → edge-creation → clustering pipeline
    on *collection* and return a metrics summary.
    """
    from entity_resolution.config.er_config import (
        BlockingConfig,
        ClusteringConfig,
        ERPipelineConfig,
        SimilarityConfig,
    )
    from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline

    db = _get_db(host, port, username, password, database)
    edge_coll = edge_collection or f"{collection}_similarity_edges"

    cfg = ERPipelineConfig(
        entity_type="generic",
        collection_name=collection,
        blocking=BlockingConfig(
            strategy=strategy,
            fields=fields or [],
            max_block_size=max_block_size,
        ),
        similarity=SimilarityConfig(
            threshold=confidence_threshold,
            edge_collection=edge_coll,
        ),
        clustering=ClusteringConfig(
            store_results=store_clusters,
            cluster_collection=f"{collection}_clusters",
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
