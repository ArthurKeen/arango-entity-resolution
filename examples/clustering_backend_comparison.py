"""
Example: Compare Clustering Backends

Demonstrates the pluggable clustering backend architecture by running
the same graph through different backends and comparing results.

Requires: ArangoDB running locally with default credentials.

    python examples/clustering_backend_comparison.py
"""

import time
from arango import ArangoClient
from entity_resolution.services.wcc_clustering_service import WCCClusteringService


def seed_test_graph(db, vertex_col="test_companies", edge_col="test_similarity"):
    """Create a small test graph with known cluster structure."""
    if db.has_collection(vertex_col):
        db.delete_collection(vertex_col)
    if db.has_collection(edge_col):
        db.delete_collection(edge_col)

    vertices = db.create_collection(vertex_col)
    edges = db.create_collection(edge_col, edge=True)

    companies = [
        {"_key": "c1", "name": "Acme Corp"},
        {"_key": "c2", "name": "ACME Corporation"},
        {"_key": "c3", "name": "Acme Inc"},
        {"_key": "c4", "name": "Globex Industries"},
        {"_key": "c5", "name": "Globex Ind."},
        {"_key": "c6", "name": "Wayne Enterprises"},
    ]
    for c in companies:
        vertices.insert(c)

    # Cluster 1: c1-c2-c3 (Acme)
    # Cluster 2: c4-c5 (Globex)
    # Cluster 3: c6 (Wayne, isolated)
    similarity_edges = [
        {"_from": f"{vertex_col}/c1", "_to": f"{vertex_col}/c2", "score": 0.92},
        {"_from": f"{vertex_col}/c2", "_to": f"{vertex_col}/c3", "score": 0.88},
        {"_from": f"{vertex_col}/c1", "_to": f"{vertex_col}/c3", "score": 0.85},
        {"_from": f"{vertex_col}/c4", "_to": f"{vertex_col}/c5", "score": 0.91},
    ]
    for e in similarity_edges:
        edges.insert(e)

    print(f"Seeded {len(companies)} vertices and {len(similarity_edges)} edges")
    return vertex_col, edge_col


def run_backend(db, edge_col, backend_name):
    """Run clustering with a specific backend and return timing + results."""
    service = WCCClusteringService(db, edge_collection=edge_col, backend=backend_name)

    start = time.time()
    clusters = service.cluster()
    elapsed = time.time() - start

    stats = service.get_statistics()
    return {
        "backend": backend_name,
        "cluster_count": len(clusters),
        "clusters": clusters,
        "elapsed_seconds": round(elapsed, 4),
        "stats": stats,
    }


def main():
    client = ArangoClient(hosts="http://localhost:8529")
    db = client.db("_system", username="root", password="rootpassword")

    vertex_col, edge_col = seed_test_graph(db)

    backends = ["python_dfs", "python_union_find", "aql_graph"]

    # Try scipy sparse if available
    try:
        import scipy  # noqa: F401
        backends.append("python_sparse")
    except ImportError:
        print("(scipy not installed — skipping python_sparse)")

    print(f"\nComparing {len(backends)} backends on {edge_col}...")
    print("=" * 60)

    results = []
    for backend in backends:
        result = run_backend(db, edge_col, backend)
        results.append(result)
        print(f"\n{backend}:")
        print(f"  Clusters found: {result['cluster_count']}")
        print(f"  Time: {result['elapsed_seconds']}s")
        for i, cluster in enumerate(result["clusters"]):
            members = [m.split("/")[-1] for m in cluster]
            print(f"    Cluster {i}: {members}")

    # Verify all backends produce identical clusters
    print("\n" + "=" * 60)
    reference = sorted([sorted(c) for c in results[0]["clusters"]])
    all_match = True
    for r in results[1:]:
        other = sorted([sorted(c) for c in r["clusters"]])
        if other != reference:
            print(f"MISMATCH: {r['backend']} differs from {results[0]['backend']}")
            all_match = False

    if all_match:
        print("All backends produced identical cluster results.")

    # Cleanup
    db.delete_collection(vertex_col)
    db.delete_collection(edge_col)


if __name__ == "__main__":
    main()
