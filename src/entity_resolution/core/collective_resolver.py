"""Collective / iterative entity resolution — plan 3.2.

Single-pass resolution scores each candidate pair independently. But a merge is
*evidence*: once A and B are judged the same entity, A inherits B's
relationships, which can push a previously-uncertain pair (A, C) over threshold
via graph-context features (plan 3.1). Collective resolution iterates:

    score pairs  →  edges (>= threshold)  →  cluster
        →  augment each record's neighbour set with its cluster-mates' neighbours
        →  re-score  →  ...  until the clustering stops changing (fixpoint) or
        max_rounds is reached.

This module is a pure orchestrator: scoring and clustering are injected as
callables, so it is fully unit-testable and reused by the pipeline with real
``BatchSimilarityService`` + graph context + a connected-components clusterer.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, FrozenSet, List, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

Pair = Tuple[str, str]
ScoredPair = Tuple[str, str, float]
NeighborCache = Dict[str, Set[str]]


def connected_components(edges: Sequence[Pair]) -> List[List[str]]:
    """Union-find connected components over key pairs (default clusterer)."""
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    groups: Dict[str, List[str]] = {}
    for node in list(parent):
        groups.setdefault(find(node), []).append(node)
    return [sorted(members) for members in groups.values()]

# score_pairs(pairs, neighbor_cache) -> [(key_a, key_b, score), ...]
ScoreFn = Callable[[Sequence[Pair], NeighborCache], List[ScoredPair]]
# cluster(edges) -> [[member_key, ...], ...]  (components; singletons allowed)
ClusterFn = Callable[[Sequence[Pair]], List[List[str]]]


class CollectiveResolver:
    def __init__(
        self,
        *,
        score_pairs: ScoreFn,
        cluster: ClusterFn,
        base_neighbor_cache: NeighborCache,
        threshold: float = 0.75,
        max_rounds: int = 5,
    ) -> None:
        self.score_pairs = score_pairs
        self.cluster = cluster
        self.base_neighbor_cache = {k: set(v) for k, v in base_neighbor_cache.items()}
        self.threshold = threshold
        self.max_rounds = max(1, int(max_rounds))

    @staticmethod
    def _signature(clusters: Sequence[Sequence[str]]) -> FrozenSet[FrozenSet[str]]:
        """Order-independent identity of a clustering, for fixpoint detection."""
        return frozenset(frozenset(c) for c in clusters if len(c) >= 2)

    def _augment(self, clusters: Sequence[Sequence[str]]) -> NeighborCache:
        """Each record inherits the union of its cluster-mates' base neighbours.

        This is the concrete 'a merge changes the graph' step: co-membership
        transfers relationships, which is what lets graph features fire on pairs
        that a single pass would miss.
        """
        cache: NeighborCache = {k: set(v) for k, v in self.base_neighbor_cache.items()}
        for comp in clusters:
            if len(comp) < 2:
                continue
            shared: Set[str] = set()
            for k in comp:
                shared |= self.base_neighbor_cache.get(k, set())
            for k in comp:
                cache[k] = cache.get(k, set()) | shared
        return cache

    def resolve(self, candidate_pairs: Sequence[Pair]) -> Dict[str, Any]:
        """Iterate to a fixpoint; returns clusters + convergence metadata."""
        cache = {k: set(v) for k, v in self.base_neighbor_cache.items()}
        seen: List[FrozenSet[FrozenSet[str]]] = []
        prev_sig = None
        clusters: List[List[str]] = []
        edges: List[Pair] = []
        rounds = 0
        converged = False
        oscillated = False

        for r in range(1, self.max_rounds + 1):
            rounds = r
            scored = self.score_pairs(candidate_pairs, cache)
            edges = [(a, b) for (a, b, s) in scored if s >= self.threshold]
            clusters = self.cluster(edges)
            sig = self._signature(clusters)

            if sig == prev_sig:
                converged = True
                break
            if sig in seen:
                # A repeated non-adjacent state => cycle; stop without a fixpoint.
                oscillated = True
                logger.warning("collective: oscillation detected at round %d; stopping", r)
                break
            seen.append(sig)
            prev_sig = sig
            cache = self._augment(clusters)

        return {
            "rounds": rounds,
            "converged": converged,
            "oscillated": oscillated,
            "clusters": clusters,
            "edges": edges,
            "num_clusters": sum(1 for c in clusters if len(c) >= 2),
        }
