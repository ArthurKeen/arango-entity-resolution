"""
Entity-level MCP tools: resolve_entity and explain_match.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import jellyfish
from arango import ArangoClient
from entity_resolution.mcp.contracts import ResolveEntityRequest
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

    return {
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
