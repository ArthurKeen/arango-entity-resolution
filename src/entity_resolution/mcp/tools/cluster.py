"""
Cluster-level MCP tools: get_clusters, merge_entities, list_collections.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from arango import ArangoClient


SYSTEM_FIELDS = {"_id", "_key", "_rev"}
TIMESTAMP_FIELDS = (
    "updated_at",
    "updatedAt",
    "created_at",
    "createdAt",
    "timestamp",
)


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
    Merge *entity_keys* into a deterministic golden-record preview.

    strategy options:
    - "most_complete": prefer the document with the most non-null fields
    - "newest": prefer the most recently inserted document
    - "first": use the first key as the canonical record
    """
    client = ArangoClient(hosts=f"http://{host}:{port}")
    db = client.db(database, username=username, password=password)
    ordered_keys = list(dict.fromkeys(entity_keys))
    if not ordered_keys:
        raise ValueError("entity_keys must contain at least one document key")

    strategy = _validate_merge_strategy(strategy)
    coll = db.collection(collection)
    docs = []
    missing_keys = []
    for key in ordered_keys:
        doc = coll.get(key)
        if doc is None:
            missing_keys.append(key)
            continue
        docs.append(doc)

    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"Documents not found in '{collection}': {missing}")

    canonical = _select_canonical_doc(docs, ordered_keys, strategy)
    golden = _merge_docs(canonical=canonical, docs=docs)
    return {
        "golden_record": golden,
        "merged_keys": ordered_keys,
        "canonical_key": canonical.get("_key"),
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


def _validate_merge_strategy(strategy: str) -> str:
    valid = {"most_complete", "newest", "first"}
    if strategy not in valid:
        opts = ", ".join(sorted(valid))
        raise ValueError(f"strategy must be one of: {opts}")
    return strategy


def _select_canonical_doc(
    docs: List[Dict[str, Any]],
    ordered_keys: List[str],
    strategy: str,
) -> Dict[str, Any]:
    docs_by_key = {doc.get("_key"): doc for doc in docs}

    if strategy == "first":
        return docs_by_key[ordered_keys[0]]

    if strategy == "newest":
        scored = []
        for idx, key in enumerate(ordered_keys):
            doc = docs_by_key.get(key)
            if doc is None:
                continue
            scored.append((_timestamp_score(doc), -idx, doc))
        newest = max(scored, key=lambda item: (item[0], item[1]))[2]
        return newest

    scored = []
    for idx, key in enumerate(ordered_keys):
        doc = docs_by_key.get(key)
        if doc is None:
            continue
        scored.append((_non_empty_field_count(doc), -idx, doc))
    return max(scored, key=lambda item: (item[0], item[1]))[2]


def _merge_docs(
    *,
    canonical: Dict[str, Any],
    docs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    merged = dict(canonical)
    for doc in docs:
        for field, value in doc.items():
            if field in SYSTEM_FIELDS:
                continue
            if _is_empty(merged.get(field)) and not _is_empty(value):
                merged[field] = value
    return merged


def _non_empty_field_count(doc: Dict[str, Any]) -> int:
    return sum(
        1
        for field, value in doc.items()
        if field not in SYSTEM_FIELDS and not _is_empty(value)
    )


def _timestamp_score(doc: Dict[str, Any]) -> float:
    for field in TIMESTAMP_FIELDS:
        value = doc.get(field)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.timestamp()
            except ValueError:
                continue
    return float("-inf")


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
