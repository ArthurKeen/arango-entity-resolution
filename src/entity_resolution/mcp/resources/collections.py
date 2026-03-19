"""
MCP Resources: ArangoDB collection and cluster data exposed as resources.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from entity_resolution.mcp.connection import get_arango_hosts


def get_collection_summary(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection_name: str,
    sample_size: int = 3,
) -> str:
    """Return a JSON summary of a collection (schema sample + doc count)."""
    from arango import ArangoClient

    client = ArangoClient(hosts=get_arango_hosts(host, port))
    db = client.db(database, username=username, password=password)

    if not db.has_collection(collection_name):
        return json.dumps({"error": f"Collection '{collection_name}' not found"})

    coll = db.collection(collection_name)
    count = coll.count()

    # Sample documents to infer schema
    cursor = db.aql.execute(
        "FOR doc IN @@col LIMIT @n RETURN doc",
        bind_vars={"@col": collection_name, "n": sample_size},
    )
    sample_docs = list(cursor)

    # Infer field types from sample
    fields: Dict[str, str] = {}
    for doc in sample_docs:
        for k, v in doc.items():
            if k.startswith("_"):
                continue
            fields[k] = type(v).__name__

    return json.dumps({
        "collection": collection_name,
        "document_count": count,
        "inferred_fields": fields,
        "sample_documents": [
            {k: v for k, v in d.items() if not k.startswith("_")}
            for d in sample_docs
        ],
    }, indent=2, default=str)


def get_cluster_detail(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    collection_name: str,
    representative_key: str,
) -> str:
    """Return the full cluster containing *representative_key*."""
    from arango import ArangoClient

    client = ArangoClient(hosts=get_arango_hosts(host, port))
    db = client.db(database, username=username, password=password)

    edge_coll = f"{collection_name}_similarity_edges"
    if not db.has_collection(edge_coll):
        return json.dumps({"error": f"No edge collection found for {collection_name}"})

    # BFS from the representative to find all cluster members
    cursor = db.aql.execute(
        """
        LET start = DOCUMENT(@start_id)
        FOR v IN 1..100 ANY start @@ec
            OPTIONS {bfs: true, uniqueVertices: 'global'}
            RETURN MERGE(KEEP(v, ATTRIBUTES(v, true)), {_id: v._id, _key: v._key})
        """,
        bind_vars={
            "@ec": edge_coll,
            "start_id": f"{collection_name}/{representative_key}",
        },
    )
    members = list(cursor)

    # Also include the representative itself
    start_doc = db.collection(collection_name).get(representative_key)
    if start_doc:
        all_members = [start_doc] + members
    else:
        all_members = members

    return json.dumps({
        "collection": collection_name,
        "representative_key": representative_key,
        "cluster_size": len(all_members),
        "members": [
            {k: v for k, v in m.items() if not k.startswith("_")} | {"_key": m.get("_key")}
            for m in all_members
        ],
    }, indent=2, default=str)
