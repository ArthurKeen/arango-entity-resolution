#!/usr/bin/env python3
"""Throughput benchmark for GraphContextSimilarity (plan 3.1).

Builds a synthetic person→hub graph, then measures:
  1. batched neighbour-set fetch time for all records (one AQL per edge collection)
  2. in-memory pair-feature join throughput over N candidate pairs

Run against any ArangoDB via env (ARANGO_HOST/PORT/ROOT_PASSWORD/USERNAME/DATABASE):

    python scripts/benchmark_graph_context.py --records 5000 --pairs 50000 --hubs 500

Temp collections are created with a random suffix and dropped afterwards.
"""
from __future__ import annotations

import argparse
import os
import random
import time
import uuid

from arango import ArangoClient

from entity_resolution.similarity.graph_context import GraphContextSimilarity


def _db():
    host = os.getenv("ARANGO_HOST", "localhost")
    port = os.getenv("ARANGO_PORT", "8529")
    user = os.getenv("ARANGO_USERNAME", "root")
    pw = os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGO_PASSWORD", "")
    database = os.getenv("ARANGO_DATABASE", "_system")
    client = ArangoClient(hosts=f"http://{host}:{port}")
    return client.db(database, username=user, password=pw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=int, default=5000)
    ap.add_argument("--pairs", type=int, default=50000)
    ap.add_argument("--hubs", type=int, default=500)
    ap.add_argument("--edges-per-record", type=int, default=3)
    args = ap.parse_args()

    db = _db()
    suffix = uuid.uuid4().hex[:8]
    person = f"bgc_person_{suffix}"
    hub = f"bgc_hub_{suffix}"
    edge = f"bgc_link_{suffix}"

    print(f"Creating {args.records} records, {args.hubs} hubs, "
          f"~{args.records * args.edges_per_record} edges ...")
    db.create_collection(person)
    db.create_collection(hub)
    db.create_collection(edge, edge=True)
    try:
        db.collection(person).insert_many(
            [{"_key": f"r{i}", "name": f"Record {i}"} for i in range(args.records)]
        )
        db.collection(hub).insert_many([{"_key": f"h{j}"} for j in range(args.hubs)])
        edges = []
        for i in range(args.records):
            for _ in range(args.edges_per_record):
                j = random.randrange(args.hubs)
                edges.append({"_from": f"{person}/r{i}", "_to": f"{hub}/h{j}"})
        for k in range(0, len(edges), 5000):
            db.collection(edge).insert_many(edges[k:k + 5000])

        gcs = GraphContextSimilarity(db, person, [edge], max_hops=2)
        keys = [f"r{i}" for i in range(args.records)]

        t0 = time.time()
        cache = gcs.batch_fetch_neighbor_sets(keys)
        fetch_s = time.time() - t0
        print(f"\nNeighbour fetch: {args.records} records in {fetch_s:.3f}s "
              f"({args.records / fetch_s:,.0f} records/s)")

        pairs = [(random.choice(keys), random.choice(keys)) for _ in range(args.pairs)]
        t1 = time.time()
        for a, b in pairs:
            gcs.pair_features(a, b, cache)
        join_s = time.time() - t1
        print(f"Pair-feature join: {args.pairs} pairs in {join_s:.3f}s "
              f"({args.pairs / join_s:,.0f} pairs/s)")
    finally:
        for n in (person, hub, edge):
            if db.has_collection(n):
                db.delete_collection(n)
        print("\nTemp collections dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
