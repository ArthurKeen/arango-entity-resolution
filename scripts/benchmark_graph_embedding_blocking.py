#!/usr/bin/env python3
"""A/B evaluation for graph-embedding blocking (plan 3.4).

Builds a synthetic graph with known communities (ground-truth = intra-community
pairs), runs graph-embedding blocking, and reports pairs-completeness (recall)
and reduction ratio — the standard blocking-quality metrics.

    python scripts/benchmark_graph_embedding_blocking.py --communities 20 --size 5

Env: ARANGO_HOST/PORT/ROOT_PASSWORD/USERNAME/DATABASE. Requires ArangoDB 3.12+
with the experimental vector index enabled.

Scale envelope: node2vec here is co-occurrence + SVD (O(n^2) memory, capped at
~10k nodes). The scale path is GraphSAGE / ArangoGraphML feeding the same ANN
blocking path.
"""
from __future__ import annotations

import argparse
import itertools
import os
import uuid

from arango import ArangoClient

from entity_resolution.similarity.ann_adapter import VectorSearchUnavailableError
from entity_resolution.strategies.graph_embedding_blocking import GraphEmbeddingBlockingStrategy


def _db():
    host = os.getenv("ARANGO_HOST", "localhost")
    port = os.getenv("ARANGO_PORT", "8529")
    user = os.getenv("ARANGO_USERNAME", "root")
    pw = os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGO_PASSWORD", "")
    database = os.getenv("ARANGO_DATABASE", "_system")
    return ArangoClient(hosts=f"http://{host}:{port}").db(database, username=user, password=pw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--communities", type=int, default=20)
    ap.add_argument("--size", type=int, default=5, help="records per community")
    ap.add_argument("--threshold", type=float, default=0.6)
    args = ap.parse_args()

    db = _db()
    sfx = uuid.uuid4().hex[:8]
    person, works = f"gebm_p_{sfx}", f"gebm_w_{sfx}"
    db.create_collection(person)
    db.create_collection(works, edge=True)
    try:
        people, edges, truth = [], [], set()
        for c in range(args.communities):
            members = [f"c{c}_{i}" for i in range(args.size)]
            people.extend({"_key": k} for k in members)
            for x, y in itertools.combinations(members, 2):
                edges.append({"_from": f"{person}/{x}", "_to": f"{person}/{y}"})
                truth.add(tuple(sorted((x, y))))
        db.collection(person).insert_many(people)
        for k in range(0, len(edges), 5000):
            db.collection(works).insert_many(edges[k:k + 5000])

        n = len(people)
        strat = GraphEmbeddingBlockingStrategy(
            db=db, collection=person, edge_collection=works,
            similarity_threshold=args.threshold, limit_per_entity=args.size * 2,
            compute_embeddings=True, create_vector_index=True,
            node2vec_params={"dimensions": 16, "walk_length": 10, "num_walks": 20},
        )
        try:
            pairs = strat.generate_candidates()
        except VectorSearchUnavailableError:
            print("SKIP: vector index unavailable (needs --experimental-vector-index).")
            return 0

        found = {tuple(sorted((p["doc1_key"], p["doc2_key"]))) for p in pairs}
        tp = len(found & truth)
        recall = tp / len(truth) if truth else 0.0
        total_possible = n * (n - 1) // 2
        reduction = (total_possible - len(found)) / total_possible if total_possible else 0.0
        print(f"records={n}  candidate_pairs={len(found)}  truth_pairs={len(truth)}")
        print(f"pairs_completeness (recall) = {recall:.3f}")
        print(f"reduction_ratio             = {reduction:.4f}")
    finally:
        for c in (person, works):
            if db.has_collection(c):
                db.delete_collection(c)
        print("Temp collections dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
