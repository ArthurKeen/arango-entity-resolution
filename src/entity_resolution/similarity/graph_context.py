"""Relationship (graph-context) features for similarity scoring — plan 3.1.

For a candidate pair, graph evidence is derived from *non-similarity* edge
collections (shared employer / address / device / phone, ...): how many
neighbours the two records share, the Jaccard of their neighbour sets, and
whether they are connected within ``max_hops``.

Design (matches the plan's perf note): **batched, never per-pair**. Fetch one
1-hop neighbour set per record in the candidate set (one AQL traversal per edge
collection over all keys), cache it, then join pair features in memory. The
features are continuous scores in ``[0, 1]`` so they slot into the
Fellegi-Sunter comparison vector as ordinary fields with their own EM-learned
m/u.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Sequence, Set

from ..utils.graph_utils import format_vertex_id

logger = logging.getLogger(__name__)

DEFAULT_FEATURES = ("shared_neighbor_count", "neighbor_jaccard", "path_within_k")

#: Graph features are namespaced so they never collide with attribute fields.
FEATURE_PREFIX = "graph_"


class GraphContextSimilarity:
    """Compute batched graph-evidence features for candidate pairs."""

    def __init__(
        self,
        db: Any,
        vertex_collection: str,
        edge_collections: Sequence[str],
        *,
        max_hops: int = 2,
        features: Sequence[str] = DEFAULT_FEATURES,
        count_saturation: int = 5,
    ) -> None:
        self.db = db
        self.vertex_collection = vertex_collection
        self.edge_collections = list(edge_collections)
        self.max_hops = int(max_hops)
        self.features = list(features)
        self.count_saturation = max(1, int(count_saturation))

    def feature_field_names(self) -> List[str]:
        """The field-score keys this service contributes (namespaced)."""
        return [FEATURE_PREFIX + f for f in self.features]

    def _vid(self, key: str) -> str:
        return format_vertex_id(key, self.vertex_collection)

    def batch_fetch_neighbor_sets(self, keys: Iterable[str]) -> Dict[str, Set[str]]:
        """Return ``{key: {neighbour_vertex_id, ...}}`` (1-hop, ANY direction).

        One traversal query per configured edge collection over *all* keys;
        results are unioned across collections. Missing collections are skipped.
        """
        unique_keys = sorted({k for k in keys if k})
        cache: Dict[str, Set[str]] = {k: set() for k in unique_keys}
        if not unique_keys:
            return cache

        for edge_coll in self.edge_collections:
            try:
                if not self.db.has_collection(edge_coll):
                    logger.debug("graph_context: edge collection %r missing; skipping", edge_coll)
                    continue
                cursor = self.db.aql.execute(
                    """
                    FOR key IN @keys
                        LET vid = CONCAT(@vc, "/", key)
                        RETURN {
                            key: key,
                            ns: (FOR v IN 1..1 ANY vid @@edges RETURN DISTINCT v._id)
                        }
                    """,
                    bind_vars={"keys": unique_keys, "vc": self.vertex_collection, "@edges": edge_coll},
                )
                for row in cursor:
                    cache[row["key"]].update(row.get("ns") or [])
            except Exception as exc:  # a bad edge collection must not kill scoring
                logger.warning("graph_context: neighbour fetch failed for %r: %s", edge_coll, exc)
        return cache

    def pair_features(
        self,
        key_a: str,
        key_b: str,
        cache: Dict[str, Set[str]],
    ) -> Dict[str, float]:
        """Graph feature scores for one pair, from a prefetched neighbour cache."""
        na = cache.get(key_a, set())
        nb = cache.get(key_b, set())
        inter = na & nb
        union = na | nb

        out: Dict[str, float] = {}
        if "shared_neighbor_count" in self.features:
            out[FEATURE_PREFIX + "shared_neighbor_count"] = min(
                len(inter), self.count_saturation
            ) / self.count_saturation
        if "neighbor_jaccard" in self.features:
            out[FEATURE_PREFIX + "neighbor_jaccard"] = (
                len(inter) / len(union) if union else 0.0
            )
        if "path_within_k" in self.features:
            # Bounded proxy for connectivity within max_hops: a direct edge
            # (length 1) or a shared neighbour (length 2). Sufficient for the
            # recommended max_hops<=2; longer paths are intentionally not walked.
            direct = self._vid(key_b) in na
            connected = direct or (self.max_hops >= 2 and bool(inter))
            out[FEATURE_PREFIX + "path_within_k"] = 1.0 if connected else 0.0
        return out
