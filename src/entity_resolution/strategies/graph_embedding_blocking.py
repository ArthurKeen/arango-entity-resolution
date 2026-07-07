"""Graph-embedding blocking strategy — plan 3.4.

Blocks candidate pairs by structural similarity: learn node2vec embeddings over
a relationship graph (shared employer / address / device / ...), write them to
the records, then use the native ArangoDB vector index (ANN via
``APPROX_NEAR_COSINE``) to pair structurally-similar nodes. This is the same ANN
mechanism as :class:`VectorBlockingStrategy`, but the vectors encode graph
topology instead of text.

Scale envelope (be honest — from ``Node2VecEmbeddingService``): the co-occurrence
+ SVD implementation is **O(n²) memory** and capped (default 10k nodes / 50k
edges). It is intended for demos and small/medium graphs; the scale path is
GraphSAGE / ArangoGraphML, which produce embeddings out-of-core and can be
dropped into this same ANN blocking path unchanged.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from arango.database import StandardDatabase

from ..services.node2vec_embedding_service import Node2VecEmbeddingService, Node2VecParams
from ..utils.constants import DEFAULT_SIMILARITY_THRESHOLD
from .base_strategy import BlockingStrategy
from .vector_blocking import VectorBlockingStrategy

_NODE2VEC_PARAM_KEYS = {"dimensions", "walk_length", "num_walks", "window_size", "seed"}


class GraphEmbeddingBlockingStrategy(BlockingStrategy):
    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        edge_collection: str,
        *,
        embedding_field: str = "node_embedding",
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        limit_per_entity: int = 20,
        blocking_field: Optional[str] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
        node2vec_params: Optional[Dict[str, Any]] = None,
        compute_embeddings: bool = True,
        create_vector_index: bool = True,
        vector_index_n_lists: Optional[int] = None,
        directed: bool = False,
        edge_min_confidence: Optional[float] = None,
        edge_method: Optional[str] = None,
        edge_limit: int = 0,
    ) -> None:
        super().__init__(db, collection, filters)
        if not edge_collection:
            raise ValueError("graph_embedding blocking requires an edge_collection")
        self.edge_collection = edge_collection
        self.embedding_field = embedding_field
        self.compute_embeddings = compute_embeddings
        self.directed = directed
        self.edge_min_confidence = edge_min_confidence
        self.edge_method = edge_method
        self.edge_limit = edge_limit

        params = {k: v for k, v in (node2vec_params or {}).items() if k in _NODE2VEC_PARAM_KEYS}
        self.node2vec_params = Node2VecParams(**params)

        # Index creation is deferred to generate_candidates() — it must run AFTER
        # the node2vec embeddings are written, not at construction time (else the
        # vector index sees an empty embedding field).
        self._create_vector_index = create_vector_index
        self._vector_index_n_lists = vector_index_n_lists

        # The ANN pairing is identical to attribute-vector blocking; reuse it.
        self._vector_strategy = VectorBlockingStrategy(
            db=db,
            collection=collection,
            embedding_field=embedding_field,
            similarity_threshold=similarity_threshold,
            limit_per_entity=limit_per_entity,
            blocking_field=blocking_field,
            filters=filters,
            create_vector_index=False,
            vector_index_n_lists=vector_index_n_lists,
        )

    def compute_and_write_embeddings(self) -> Dict[str, Any]:
        """Learn node2vec embeddings from the graph and write them to records."""
        svc = Node2VecEmbeddingService(
            db=self.db,
            edge_collection=self.edge_collection,
            vertex_collection=self.collection,
            embedding_field=self.embedding_field,
            directed=self.directed,
        )
        edges = svc.fetch_edges(
            limit=self.edge_limit,
            min_confidence=self.edge_min_confidence,
            method=self.edge_method,
        )
        if not edges:
            return {"embeddings_written": 0, "reason": "no edges in graph"}
        embeddings = svc.train_embeddings(edges, self.node2vec_params)
        return svc.write_embeddings(embeddings, params=self.node2vec_params)

    def generate_candidates(self) -> List[Dict[str, Any]]:
        start = time.time()
        embed_stats = None
        if self.compute_embeddings:
            embed_stats = self.compute_and_write_embeddings()

        # Build the vector index now that embeddings exist on the records.
        if self._create_vector_index:
            self._vector_strategy.ensure_vector_index(n_lists=self._vector_index_n_lists)

        pairs = self._vector_strategy.generate_candidates()

        self._stats.update(self._vector_strategy.get_statistics())
        self._stats["strategy_name"] = self.__class__.__name__
        self._stats["total_pairs"] = len(pairs)
        self._stats["execution_time_seconds"] = round(time.time() - start, 4)
        self._stats["timestamp"] = datetime.now().isoformat()
        if embed_stats is not None:
            self._stats["embedding"] = embed_stats
        return pairs
