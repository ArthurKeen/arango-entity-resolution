"""
Cluster-level MCP tools: get_clusters, merge_entities, list_collections.
"""
from __future__ import annotations

from typing import Any, Dict, List

from arango import ArangoClient


def run_get_clusters(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection: str,
    limit: int = 50,
    min_size: int = 2,
) -> List[Dict[str, Any]]:
    """
    Return entity clusters from the graph for *collection*.
    Each cluster is a list of document keys that were resolved to represent
    the same real-world entity.
    """

    client = ArangoClient(hosts=f"http://{host}:{port}")
    db = client.db(database, username=username, password=password)

    edge_coll = f"{collection}_similarity_edges"
    if not db.has_collection(edge_coll):
        return []

    # Run a WCC query inline — small enough for MCP response sizes
    aql = """
    FOR v, e, p IN 1..100 OUTBOUND
        (FOR doc IN @@col LIMIT 1 RETURN doc)[0]
        @@edge_col OPTIONS {bfs: true, uniqueVertices: 'global'}
        COLLECT cluster = p.vertices[0]._key INTO members
        FILTER LENGTH(members) >= @min_size
        SORT LENGTH(members) DESC
        LIMIT @limit
        RETURN {
            representative: cluster,
            members: members[*].v._key,
            size: LENGTH(members)
        }
    """
    # Simpler approach: use WCCClusteringService
    from entity_resolution.services.wcc_clustering_service import WCCClusteringService

    svc = WCCClusteringService(db=db, edge_collection=edge_coll)
    clusters: list = svc.find_clusters()

    result = []
    for cluster in clusters:
        if len(cluster) >= min_size:
            result.append({"members": list(cluster), "size": len(cluster)})
        if len(result) >= limit:
            break

    return sorted(result, key=lambda c: c["size"], reverse=True)


def run_merge_entities(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection: str,
    entity_keys: List[str],
    strategy: str = "most_complete",
) -> Dict[str, Any]:
    """
    Merge *entity_keys* into a single golden record in *collection*.

    strategy options:
    - "most_complete": prefer the document with the most non-null fields
    - "newest": prefer the most recently inserted document
    - "first": use the first key as the canonical record
    """
    from entity_resolution.services.golden_record_service import GoldenRecordService

    client = ArangoClient(hosts=f"http://{host}:{port}")
    db = client.db(database, username=username, password=password)

    svc = GoldenRecordService(db=db, collection_name=collection)
    golden = svc.create_golden_record(
        entity_keys=entity_keys,
        merge_strategy=strategy,
    )
    return {
        "golden_record": golden,
        "merged_keys": entity_keys,
        "strategy_used": strategy,
    }


def run_list_collections(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
) -> List[Dict[str, Any]]:
    """List all document collections in the database with document counts."""

    client = ArangoClient(hosts=f"http://{host}:{port}")
    db = client.db(database, username=username, password=password)

    collections = []
    for coll in db.collections():
        if coll["system"]:
            continue
        try:
            count = db.collection(coll["name"]).count()
        except Exception:
            count = -1
        collections.append({
            "name": coll["name"],
            "type": "edge" if coll["type"] == 3 else "document",
            "count": count,
        })

    return sorted(collections, key=lambda c: c["name"])
