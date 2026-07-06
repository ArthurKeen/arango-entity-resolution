#!/usr/bin/env python3
"""Collective vs single-pass resolution benchmark (plan 3.2).

Builds a synthetic relationship-rich graph where each "true entity" has several
records, one of which lacks the shared relationship (so only a merge can pull it
in). Reports clusters recovered + rounds + time for single-pass vs collective.

    python scripts/benchmark_collective.py --entities 200 --records-per-entity 4

Env: ARANGO_HOST/PORT/ROOT_PASSWORD/USERNAME/DATABASE.
"""
from __future__ import annotations

import argparse
import os
import time
import uuid

from arango import ArangoClient

from entity_resolution.core.collective_resolver import CollectiveResolver, connected_components
from entity_resolution.services.batch_similarity_service import BatchSimilarityService
from entity_resolution.similarity.graph_context import GraphContextSimilarity


def _db():
    host = os.getenv("ARANGO_HOST", "localhost")
    port = os.getenv("ARANGO_PORT", "8529")
    user = os.getenv("ARANGO_USERNAME", "root")
    pw = os.getenv("ARANGO_ROOT_PASSWORD") or os.getenv("ARANGO_PASSWORD", "")
    database = os.getenv("ARANGO_DATABASE", "_system")
    return ArangoClient(hosts=f"http://{host}:{port}").db(database, username=user, password=pw)


class _MaxFS:
    def score(self, fs):
        return max(fs.get("name", 0.0), fs.get("graph_neighbor_jaccard", 0.0),
                   fs.get("graph_path_within_k", 0.0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", type=int, default=200)
    ap.add_argument("--records-per-entity", type=int, default=4)
    args = ap.parse_args()

    db = _db()
    sfx = uuid.uuid4().hex[:8]
    person, org, works = f"bc_p_{sfx}", f"bc_o_{sfx}", f"bc_w_{sfx}"
    db.create_collection(person)
    db.create_collection(org)
    db.create_collection(works, edge=True)
    try:
        people, orgs, edges, pairs = [], [], [], []
        for e in range(args.entities):
            orgs.append({"_key": f"o{e}"})
            keys = [f"e{e}_r{i}" for i in range(args.records_per_entity)]
            for i, k in enumerate(keys):
                # r0 and r1 share a near-identical name (the seed match); the
                # rest have distinct names so only the *shared employer* links
                # them — and only after r0 inherits it via the r0~r1 merge.
                if i <= 1:
                    name = f"Entity {e} Incorporated"
                else:
                    name = f"Division {e}x{i} Holdings"
                people.append({"_key": k, "name": name})
                if i >= 1:  # every record except r0 carries the shared employer
                    edges.append({"_from": f"{person}/{k}", "_to": f"{org}/o{e}"})
            for i in range(1, len(keys)):
                pairs.append((keys[0], keys[i]))
        db.collection(person).insert_many(people)
        db.collection(org).insert_many(orgs)
        for k in range(0, len(edges), 5000):
            db.collection(works).insert_many(edges[k:k + 5000])

        gc = GraphContextSimilarity(db, person, [works], max_hops=2)
        sim = BatchSimilarityService(
            db=db, collection=person, field_weights={"name": 1.0},
            scoring_method="fellegi_sunter", fs_scorer=_MaxFS(), graph_context=gc,
        )
        base = gc.batch_fetch_neighbor_sets({k for p in pairs for k in p})

        def score_fn(prs, cache):
            return sim.compute_similarities(list(prs), threshold=0.0, return_all=True, neighbor_cache=cache)

        for label, rounds in (("single-pass", 1), ("collective", 5)):
            t0 = time.time()
            res = CollectiveResolver(
                score_pairs=score_fn, cluster=connected_components,
                base_neighbor_cache=base, threshold=0.95, max_rounds=rounds,
            ).resolve(pairs)
            dt = time.time() - t0
            full = sum(1 for c in res["clusters"] if len(c) == args.records_per_entity)
            print(f"{label:12s}: {res['num_clusters']:4d} clusters "
                  f"({full} fully recovered), rounds={res['rounds']}, "
                  f"converged={res['converged']}, {dt:.2f}s")
    finally:
        for n in (person, org, works):
            if db.has_collection(n):
                db.delete_collection(n)
        print("Temp collections dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
