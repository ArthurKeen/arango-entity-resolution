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
    Return entity clusters for *collection*.

    Reads from the stored cluster collection (populated by find_duplicates).
    Falls back to a WCC graph query if no stored clusters exist yet.
    """
    client = ArangoClient(hosts=f"http://{host}:{port}")
    db = client.db(database, username=username, password=password)

    # Try stored cluster collections in order of convention
    for cluster_coll_name in (f"{collection}_clusters", "entity_clusters"):
        if not db.has_collection(cluster_coll_name):
            continue
        try:
            cursor = db.aql.execute(
                """
                FOR c IN @@coll
                    FILTER LENGTH(c.members) >= @min_size
                    SORT LENGTH(c.members) DESC
                    LIMIT @limit
                    RETURN {
                        cluster_id: c._key,
                        members: c.members,
                        size: LENGTH(c.members),
                        representative: c.representative
                    }
                """,
                bind_vars={"@coll": cluster_coll_name, "min_size": min_size, "limit": limit},
            )
            results = list(cursor)
            if results:
                return results
        except Exception:
            continue

    # Fallback: AQL WCC graph traversal on the similarity edge collection
    edge_coll = f"{collection}_similarity_edges"
    if not db.has_collection(edge_coll):
        return []

    try:
        cursor = db.aql.execute(
            """
            LET edges = (FOR e IN @@edge_coll RETURN e)
            LET vertices = UNIQUE(
                APPEND(edges[*]._from, edges[*]._to)
            )
            RETURN {vertices: vertices, edge_count: LENGTH(edges)}
            """,
            bind_vars={"@edge_coll": edge_coll},
        )
        stats = list(cursor)
        return [{"info": "Run find_duplicates first to generate clusters", "stats": stats}]
    except Exception:
        return []



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
