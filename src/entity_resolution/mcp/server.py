"""
arango-entity-resolution MCP Server

Exposes entity resolution as MCP tools and resources so AI agents can
perform ER through natural language without writing any code.

Entry point: `arango-er-mcp` (stdio) or `arango-er-mcp --transport sse`
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server & connection config
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="arango-entity-resolution",
    instructions=(
        "You have access to an ArangoDB entity resolution system. "
        "Use the tools to find duplicate records, resolve entities, explain "
        "why two records match, and manage entity clusters. "
        "Always call `list_collections` first if you are unsure which "
        "collection to use."
    ),
)

def _conn() -> Dict[str, Any]:
    """Read connection settings from environment variables."""
    return dict(
        host=os.getenv("ARANGO_HOST", "localhost"),
        port=int(os.getenv("ARANGO_PORT", "8529")),
        username=os.getenv("ARANGO_USERNAME", "root"),
        password=os.getenv("ARANGO_PASSWORD", os.getenv("ARANGO_ROOT_PASSWORD", "")),
        database=os.getenv("ARANGO_DATABASE", "_system"),
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_collections() -> List[Dict[str, Any]]:
    """
    List all document and edge collections in the ArangoDB database.

    Returns each collection's name, type ("document" or "edge"), and
    document count. Call this first to discover available collections.
    """
    from entity_resolution.mcp.tools.cluster import run_list_collections
    return run_list_collections(**_conn())


@mcp.tool()
def find_duplicates(
    collection: str,
    fields: List[str],
    strategy: str = "exact",
    confidence_threshold: float = 0.85,
    max_block_size: int = 500,
    store_clusters: bool = True,
    edge_collection: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the full entity resolution pipeline on a collection.

    Performs blocking → similarity computation → edge creation → clustering.
    Returns a metrics summary with counts and runtimes for each phase.

    Args:
        collection: Name of the ArangoDB document collection to deduplicate.
        fields: List of field names to use for blocking and similarity.
        strategy: Blocking strategy — "exact" (default) or "bm25".
        confidence_threshold: Minimum similarity score to create an edge (0–1).
        max_block_size: Maximum block size for blocking phase.
        store_clusters: Whether to persist cluster results to ArangoDB.
        edge_collection: Target edge collection name (default: {collection}_similarity_edges).
    """
    from entity_resolution.mcp.tools.pipeline import run_find_duplicates
    return run_find_duplicates(
        **_conn(),
        collection=collection,
        strategy=strategy,
        fields=fields,
        confidence_threshold=confidence_threshold,
        max_block_size=max_block_size,
        store_clusters=store_clusters,
        edge_collection=edge_collection,
    )


@mcp.tool()
def pipeline_status(
    collection: str,
    edge_collection: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get the current entity resolution status for a collection.

    Returns total document count, edge statistics (inferred vs direct,
    average confidence), and cluster count.

    Args:
        collection: Name of the document collection.
        edge_collection: Edge collection name (default: {collection}_similarity_edges).
    """
    from entity_resolution.mcp.tools.pipeline import run_pipeline_status
    return run_pipeline_status(**_conn(), collection=collection, edge_collection=edge_collection)


@mcp.tool()
def resolve_entity(
    collection: str,
    record: Dict[str, Any],
    fields: List[str],
    confidence_threshold: float = 0.80,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Find existing records in a collection that match a given record.

    Does NOT modify the database — purely a read/search operation.
    Returns a ranked list of candidate matches with similarity scores.

    Args:
        collection: Collection to search for matches.
        record: The record to find matches for (a dict of field→value).
        fields: Fields to use for blocking and similarity comparison.
        confidence_threshold: Minimum score for a result to be included.
        top_k: Maximum number of matches to return.
    """
    from entity_resolution.mcp.tools.entity import run_resolve_entity
    return run_resolve_entity(
        **_conn(),
        collection=collection,
        record=record,
        fields=fields,
        confidence_threshold=confidence_threshold,
        top_k=top_k,
    )


@mcp.tool()
def explain_match(
    collection: str,
    key_a: str,
    key_b: str,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Explain why (or why not) two entities in a collection match.

    Returns a field-level similarity breakdown showing individual scores
    for each field, the overall score, and an interpretation.

    Args:
        collection: Collection both documents belong to.
        key_a: _key of the first document.
        key_b: _key of the second document.
        fields: Specific fields to compare (default: all shared string fields).
    """
    from entity_resolution.mcp.tools.entity import run_explain_match
    return run_explain_match(**_conn(), collection=collection, key_a=key_a, key_b=key_b, fields=fields)


@mcp.tool()
def get_clusters(
    collection: str,
    limit: int = 50,
    min_size: int = 2,
) -> List[Dict[str, Any]]:
    """
    Return entity clusters found in the collection's similarity graph.

    Each cluster is a group of document keys that were resolved to
    represent the same real-world entity, sorted by cluster size descending.

    Args:
        collection: Document collection name.
        limit: Maximum number of clusters to return.
        min_size: Minimum cluster size to include.
    """
    from entity_resolution.mcp.tools.cluster import run_get_clusters
    return run_get_clusters(**_conn(), collection=collection, limit=limit, min_size=min_size)


@mcp.tool()
def merge_entities(
    collection: str,
    entity_keys: List[str],
    strategy: str = "most_complete",
) -> Dict[str, Any]:
    """
    Merge multiple entity records into a single golden record.

    Args:
        collection: Collection containing the entities.
        entity_keys: List of document _keys to merge.
        strategy: Merge strategy — "most_complete" (default), "newest", or "first".
    """
    from entity_resolution.mcp.tools.cluster import run_merge_entities
    return run_merge_entities(
        **_conn(),
        collection=collection,
        entity_keys=entity_keys,
        strategy=strategy,
    )


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("arango://collections/{collection_name}/summary")
def collection_summary(collection_name: str) -> str:
    """
    JSON summary of a collection: document count, inferred field schema,
    and sample documents.
    """
    from entity_resolution.mcp.resources.collections import get_collection_summary
    return get_collection_summary(**_conn(), collection_name=collection_name)


@mcp.resource("arango://clusters/{collection_name}/{representative_key}")
def cluster_detail(collection_name: str, representative_key: str) -> str:
    """
    Full details of the entity cluster containing *representative_key*,
    including all member documents.
    """
    from entity_resolution.mcp.resources.collections import get_cluster_detail
    return get_cluster_detail(
        **_conn(),
        collection_name=collection_name,
        representative_key=representative_key,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="arango-er-mcp",
        description="Entity Resolution MCP Server for ArangoDB",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8080, help="Port for SSE transport")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE transport")
    args = parser.parse_args()

    if args.transport == "sse":
        mcp.settings.port = args.port
        mcp.settings.host = args.host
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
