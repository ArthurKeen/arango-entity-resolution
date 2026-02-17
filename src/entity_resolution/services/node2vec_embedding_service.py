"""
Node embeddings (Node2Vec-style) for small graphs.

IMPORTANT CAVEAT
---------------
This implementation is intentionally simple and is NOT suitable for large-scale graphs
(e.g., millions/billions of edges). It uses an in-memory co-occurrence matrix and an
SVD-based factorization, which is inherently limited by O(n^2) memory in the number
of vertices.

Use this for:
- Prototyping Phase 3 node embeddings on small graphs
- Demonstrations and offline analysis
- Validating downstream vector search integration (store embeddings in ArangoDB)

Do NOT use this for:
- Production-scale graphs
- Billion-edge ArangoDB deployments

For large graphs, you typically need sampling-based GNN training (e.g., GraphSAGE)
and a distributed training / partitioned adjacency pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import logging

import numpy as np
from arango.collection import Collection
from arango.database import StandardDatabase

from ..utils.constants import PHASE3_NODE_EMBEDDING_LIMITS
from ..utils.validation import validate_collection_name


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Node2VecParams:
    dimensions: int = 64
    walk_length: int = 10
    num_walks: int = 10
    window_size: int = 5
    seed: int = 42


class Node2VecEmbeddingService:
    """
    Train and persist Node2Vec-style node embeddings for a graph stored in ArangoDB.

    This service:
    - Fetches edges from an ArangoDB edge collection
    - Generates uniform random walks over the graph
    - Builds a co-occurrence matrix from walk windows
    - Computes SVD embeddings (small-graph approximation)
    - Writes embeddings back onto vertex documents
    """

    def __init__(
        self,
        db: StandardDatabase,
        edge_collection: str,
        vertex_collection: Optional[str] = None,
        embedding_field: str = "node_embedding",
        embedding_meta_field: str = "node_embedding_meta",
        directed: bool = False,
        safety_limits: Optional[Dict[str, int]] = None,
    ) -> None:
        self.db = db
        self.edge_collection = validate_collection_name(edge_collection)
        self.vertex_collection = vertex_collection
        self.embedding_field = embedding_field
        self.embedding_meta_field = embedding_meta_field
        self.directed = directed
        self.safety_limits = {**PHASE3_NODE_EMBEDDING_LIMITS, **(safety_limits or {})}

    def fetch_edges(
        self,
        *,
        limit: int = 0,
        min_confidence: Optional[float] = None,
        method: Optional[str] = None,
    ) -> List[Tuple[str, str, float]]:
        """
        Fetch edges from ArangoDB.

        Args:
            limit: Max edges to fetch (0 = no limit). For safety, prefer a limit.
            min_confidence: Optional minimum e.confidence filter (if field exists).
            method: Optional e.method filter (if field exists).

        Returns:
            List of (from_id, to_id, weight) edges. Weight defaults to 1.0 if no confidence.
        """
        max_edges = int(self.safety_limits['max_edges_fetched'])
        warn_edges = int(self.safety_limits['warn_edges_threshold'])
        if limit and limit > max_edges:
            raise ValueError(f"limit={limit} exceeds max_edges_fetched={max_edges} (prototype safety limit)")

        # Safe-by-default: if limit is not provided, cap to the hard limit.
        if not limit or limit <= 0:
            limit = max_edges
            logger.warning(
                "fetch_edges called with limit=0; capping to max_edges_fetched=%s (prototype safety limit)",
                max_edges,
            )

        if not self.db.has_collection(self.edge_collection):
            raise ValueError(f"Edge collection '{self.edge_collection}' does not exist")

        filters: List[str] = []
        bind_vars: Dict[str, Any] = {}

        if method is not None:
            filters.append("e.method == @method")
            bind_vars["method"] = method

        if min_confidence is not None:
            # If edges do not have confidence, this will simply filter everything out.
            filters.append("e.confidence != null AND e.confidence >= @min_confidence")
            bind_vars["min_confidence"] = float(min_confidence)

        filter_clause = ""
        if filters:
            filter_clause = "FILTER " + " AND ".join(filters)

        limit_clause = ""
        if limit and limit > 0:
            limit_clause = "LIMIT @limit"
            bind_vars["limit"] = int(limit)

        query = f"""
        FOR e IN {self.edge_collection}
            {filter_clause}
            {limit_clause}
            RETURN {{
                _from: e._from,
                _to: e._to,
                w: (e.confidence != null ? e.confidence : 1.0)
            }}
        """

        cursor = self.db.aql.execute(query, bind_vars=bind_vars)
        out: List[Tuple[str, str, float]] = []
        for row in cursor:
            out.append((row["_from"], row["_to"], float(row.get("w", 1.0))))

        if len(out) > max_edges:
            raise ValueError(
                f"Fetched {len(out)} edges which exceeds max_edges_fetched={max_edges} (prototype safety limit)"
            )
        if len(out) > warn_edges:
            logger.warning(
                "Fetched %s edges (warn_edges_threshold=%s). This prototype may be slow or memory-hungry.",
                len(out),
                warn_edges,
            )
        return out

    def train_embeddings(
        self,
        edges: Sequence[Tuple[str, str, float]],
        params: Node2VecParams,
    ) -> Dict[str, List[float]]:
        """
        Train embeddings from an edge list.

        Returns:
            dict mapping node_id -> embedding vector (list[float])
        """
        max_dims = int(self.safety_limits['max_dimensions'])
        if params.dimensions <= 0:
            raise ValueError("dimensions must be > 0")
        if params.dimensions > max_dims:
            raise ValueError(f"dimensions={params.dimensions} exceeds max_dimensions={max_dims} (prototype safety limit)")
        if params.walk_length <= 0 or params.num_walks <= 0:
            raise ValueError("walk_length and num_walks must be > 0")
        if params.window_size <= 0:
            raise ValueError("window_size must be > 0")

        adjacency = self._build_adjacency(edges, directed=self.directed)
        nodes = sorted(adjacency.keys())
        if not nodes:
            return {}

        max_nodes = int(self.safety_limits['max_nodes'])
        warn_nodes = int(self.safety_limits['warn_nodes_threshold'])
        if len(nodes) > max_nodes:
            raise ValueError(f"node_count={len(nodes)} exceeds max_nodes={max_nodes} (prototype safety limit)")
        if len(nodes) > warn_nodes:
            logger.warning(
                "Training embeddings for %s nodes (warn_nodes_threshold=%s). This prototype may be slow or memory-hungry.",
                len(nodes),
                warn_nodes,
            )

        est_bytes = self._estimate_cooccurrence_bytes(len(nodes))
        logger.info(
            "Estimated co-occurrence matrix size: ~%s MB for %s nodes (float32)",
            int(est_bytes / (1024 * 1024)),
            len(nodes),
        )

        rng = np.random.default_rng(params.seed)
        walks = self._generate_walks(
            nodes=nodes,
            adjacency=adjacency,
            walk_length=params.walk_length,
            num_walks=params.num_walks,
            rng=rng,
        )

        cooc = self._cooccurrence_matrix(
            walks=walks,
            nodes=nodes,
            window_size=params.window_size,
        )

        # If cooc is all zeros (e.g., isolated nodes), return zero vectors.
        if float(cooc.sum()) == 0.0:
            dim = min(params.dimensions, len(nodes))
            return {n: [0.0] * dim for n in nodes}

        # SVD factorization: cooc ~= U S V^T. Use U * sqrt(S) as embeddings.
        # This is a small-graph approximation and scales poorly.
        u, s, _vt = np.linalg.svd(cooc, full_matrices=False)
        dim = min(params.dimensions, u.shape[1])
        emb = u[:, :dim] * np.sqrt(s[:dim])

        # Normalize vectors
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        emb = emb / norms

        return {node: emb[i].astype(float).tolist() for i, node in enumerate(nodes)}

    def write_embeddings(
        self,
        embeddings: Dict[str, List[float]],
        *,
        params: Node2VecParams,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """
        Write embeddings back to vertex documents in ArangoDB.

        Node IDs are expected to be full Arango IDs like "collection/key".
        If vertex_collection was provided to this service, all IDs are assumed to belong
        to that collection and keys are extracted from the id.
        """
        if not embeddings:
            return {"updated": 0, "collections": {}}
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")

        docs_by_collection: Dict[str, List[Dict[str, Any]]] = {}
        for node_id, vector in embeddings.items():
            if "/" not in node_id:
                # Allow passing keys if vertex_collection is set
                if not self.vertex_collection:
                    raise ValueError(f"Invalid node id '{node_id}'. Expected 'collection/key'.")
                coll = self.vertex_collection
                key = node_id
            else:
                coll, key = node_id.split("/", 1)
                if self.vertex_collection:
                    coll = self.vertex_collection

            docs_by_collection.setdefault(coll, []).append(
                {
                    "_key": key,
                    self.embedding_field: vector,
                    self.embedding_meta_field: {
                        "method": "node2vec_svd",
                        "dimensions": params.dimensions,
                        "walk_length": params.walk_length,
                        "num_walks": params.num_walks,
                        "window_size": params.window_size,
                        "seed": params.seed,
                    },
                }
            )

        updated = 0
        per_coll: Dict[str, int] = {}
        for coll_name, docs in docs_by_collection.items():
            if not self.db.has_collection(coll_name):
                raise ValueError(f"Vertex collection '{coll_name}' does not exist")
            coll: Collection = self.db.collection(coll_name)

            coll_updated = 0
            for i in range(0, len(docs), batch_size):
                batch = docs[i : i + batch_size]
                # merge=True preserves other fields; silent avoids returning docs
                coll.update_many(batch, silent=True, merge=True)
                coll_updated += len(batch)
            per_coll[coll_name] = coll_updated
            updated += coll_updated

        return {"updated": updated, "collections": per_coll}

    @staticmethod
    def _build_adjacency(
        edges: Sequence[Tuple[str, str, float]],
        *,
        directed: bool,
    ) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {}
        for a, b, _w in edges:
            adj.setdefault(a, []).append(b)
            if not directed:
                adj.setdefault(b, []).append(a)
            else:
                adj.setdefault(b, [])
        return adj

    @staticmethod
    def _generate_walks(
        *,
        nodes: Sequence[str],
        adjacency: Dict[str, List[str]],
        walk_length: int,
        num_walks: int,
        rng: np.random.Generator,
    ) -> List[List[str]]:
        walks: List[List[str]] = []
        for _ in range(num_walks):
            for start in nodes:
                walk = [start]
                current = start
                for _step in range(walk_length - 1):
                    nbrs = adjacency.get(current, [])
                    if not nbrs:
                        break
                    current = nbrs[int(rng.integers(0, len(nbrs)))]
                    walk.append(current)
                walks.append(walk)
        return walks

    @staticmethod
    def _cooccurrence_matrix(
        *,
        walks: Iterable[Sequence[str]],
        nodes: Sequence[str],
        window_size: int,
    ) -> np.ndarray:
        idx = {n: i for i, n in enumerate(nodes)}
        n = len(nodes)
        mat = np.zeros((n, n), dtype=np.float32)

        for walk in walks:
            w = list(walk)
            for i, center in enumerate(w):
                ci = idx.get(center)
                if ci is None:
                    continue
                left = max(0, i - window_size)
                right = min(len(w), i + window_size + 1)
                for j in range(left, right):
                    if j == i:
                        continue
                    ctx = w[j]
                    cj = idx.get(ctx)
                    if cj is None:
                        continue
                    mat[ci, cj] += 1.0

        # Symmetrize to stabilize SVD for undirected graphs
        mat = 0.5 * (mat + mat.T)
        return mat

    @staticmethod
    def _estimate_cooccurrence_bytes(node_count: int) -> int:
        # float32 co-occurrence matrix: n*n*4 bytes (does not include SVD workspace)
        if node_count <= 0:
            return 0
        return int(node_count) * int(node_count) * 4

