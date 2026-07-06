"""Incremental cluster maintenance — plan 3.3.

Extends single-record resolution from "find matches" to "maintain clusters":
a new or updated record is blocked, scored, linked to its matches, and its
connected component is re-clustered via the scoped re-clusterer (plan 0.1) —
without reprocessing the whole collection.

Key properties:
- **Honours human verdicts.** Similarity edges are upserted under the same
  deterministic (sorted-endpoint) key ``FeedbackApplicationService`` uses, with
  an ``UPDATE {}`` no-op, so a previously suppressed/confirmed edge is never
  overwritten or resurrected.
- **Sequence-neutral.** Edge keys are content-addressed and the re-cluster
  recomputes connected components from the full active edge set, so committing
  records in any order converges to the same final clusters.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..services.feedback_application_service import (
    FeedbackApplicationError,
    FeedbackApplicationService,
)
from ..utils.graph_utils import format_vertex_id
from .incremental_resolver import IncrementalResolver

logger = logging.getLogger(__name__)


class IncrementalMaintainer:
    def __init__(
        self,
        db: Any,
        collection: str,
        fields: List[str],
        *,
        edge_collection: str,
        cluster_collection: str,
        golden_collection: Optional[str] = None,
        confidence_threshold: float = 0.80,
        blocking_strategy: str = "prefix",
        prefix_length: int = 3,
    ) -> None:
        self.db = db
        self.collection = collection
        self.edge_collection = edge_collection
        self.resolver = IncrementalResolver(
            db, collection, fields,
            confidence_threshold=confidence_threshold,
            blocking_strategy=blocking_strategy,
            prefix_length=prefix_length,
        )
        self.applier = FeedbackApplicationService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=collection,
            cluster_collection=cluster_collection,
            golden_collection=golden_collection,
        )

    @staticmethod
    def _edge_key(from_id: str, to_id: str) -> str:
        a, b = (from_id, to_id) if from_id < to_id else (to_id, from_id)
        return hashlib.md5(f"{a}->{b}".encode("utf-8")).hexdigest()

    def _upsert_similarity_edge(self, key_a: str, key_b: str, score: float) -> None:
        """Insert a canonical similarity edge iff none exists (no-op on update).

        The ``UPDATE {}`` preserves any existing edge — crucially, a human
        ``suppressed``/``confirmed`` edge is left exactly as-is.
        """
        from_id = format_vertex_id(key_a, self.collection)
        to_id = format_vertex_id(key_b, self.collection)
        c_from, c_to = (from_id, to_id) if from_id < to_id else (to_id, from_id)
        edge_key = self._edge_key(from_id, to_id)
        self.db.aql.execute(
            """
            UPSERT { _key: @key }
            INSERT @doc
            UPDATE {}
            IN @@edges
            """,
            bind_vars={
                "key": edge_key,
                "doc": {
                    "_key": edge_key, "_from": c_from, "_to": c_to,
                    "similarity": round(score, 4), "method": "incremental",
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                "@edges": self.edge_collection,
            },
        )

    def resolve_and_commit(
        self,
        key: str,
        *,
        top_k: int = 25,
        auto_refresh: bool = False,
        stamp: bool = True,
    ) -> Dict[str, Any]:
        """Resolve one record against the collection and update its cluster.

        Returns ``{key, matches, recluster}``. Raises ``KeyError`` if the record
        does not exist, ``FeedbackApplicationError`` on lock contention.
        """
        doc = self.db.collection(self.collection).get(key)
        if doc is None:
            raise KeyError(f"record '{key}' not found in {self.collection}")

        matches = self.resolver.resolve(doc, top_k=top_k, exclude_key=key)
        match_keys = [m["_key"] for m in matches]

        # Serialize per-component work with the same TTL lock the verdict loop
        # uses, so a concurrent verdict/edit cannot interleave re-cluster writes.
        lock_key = self.applier._acquire_lock(key)
        if lock_key is None:
            raise FeedbackApplicationError(
                f"component for '{key}' is locked by a concurrent operation; retry"
            )
        try:
            for m in matches:
                self._upsert_similarity_edge(key, m["_key"], m["score"])
            recluster = self.applier.recluster_component(
                key, *match_keys, auto_refresh=auto_refresh
            )
        finally:
            self.applier._release_lock(lock_key)

        if stamp:
            try:
                self.db.collection(self.collection).update(
                    {"_key": key, "_er_resolved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                )
            except Exception:
                pass

        return {"key": key, "matches": matches, "recluster": recluster}

    def pending_keys(self, limit: int = 100) -> List[str]:
        """Keys of records not yet resolved (no ``_er_resolved_at`` stamp)."""
        cursor = self.db.aql.execute(
            """
            FOR d IN @@col
                FILTER d._er_resolved_at == null
                LIMIT @limit
                RETURN d._key
            """,
            bind_vars={"@col": self.collection, "limit": int(limit)},
        )
        return list(cursor)
