"""
Async/streaming ER pipeline.

Wraps the synchronous ConfigurableERPipeline in asyncio so callers can:
- Await the full pipeline without blocking the event loop
- Iterate pipeline stages as they complete (async generator)
- Run blocking + similarity concurrently in a thread pool

Usage (await full run)::

    pipeline = AsyncERPipeline(db, config=cfg)
    results = await pipeline.run()

Usage (streaming stages)::

    async for stage_name, stage_result in pipeline.run_streaming():
        print(f"{stage_name}: {stage_result}")

Usage (concurrent blocking strategies)::

    candidates = await pipeline.run_blocking_concurrent(
        strategies=["exact", "bm25", "vector"]
    )
"""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# Shared executor — reused across pipeline instances for efficiency
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="arango-er")


class AsyncERPipeline:
    """
    Async wrapper around ``ConfigurableERPipeline``.

    All database-touching operations run in a thread-pool executor so they
    never block the asyncio event loop.  Concurrent blocking strategies are
    gathered with ``asyncio.gather``, cutting multi-strategy runs to the
    duration of the slowest strategy instead of their sum.

    Parameters
    ----------
    db:
        An authenticated python-arango ``Database`` handle.
    config:
        An ``ERPipelineConfig`` instance.
    config_path:
        Path to a YAML/JSON config file (used if *config* is not provided).
    executor:
        Optional ``ThreadPoolExecutor`` to use.  Defaults to the module-level
        shared executor.
    progress_callback:
        Optional ``async`` callable ``(stage: str, result: dict) -> None``
        called after each stage completes.
    """

    def __init__(
        self,
        db,
        config=None,
        config_path: Optional[Union[str, Path]] = None,
        executor: Optional[ThreadPoolExecutor] = None,
        progress_callback=None,
    ) -> None:
        from entity_resolution.config.er_config import ERPipelineConfig

        self.db = db
        self.executor = executor or _EXECUTOR
        self.progress_callback = progress_callback

        if config is not None:
            self.config = config
        elif config_path is not None:
            config_path = Path(config_path)
            if config_path.suffix.lower() == ".json":
                self.config = ERPipelineConfig.from_json(config_path)
            else:
                self.config = ERPipelineConfig.from_yaml(config_path)
        else:
            raise ValueError("Either config or config_path must be provided")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> Dict[str, Any]:
        """
        Run the full ER pipeline asynchronously.

        Equivalent to ``ConfigurableERPipeline.run()`` but non-blocking.
        Returns the same metrics dict.
        """
        results: Dict[str, Any] = {}
        async for stage, result in self.run_streaming():
            results[stage] = result
        return results

    async def run_streaming(self) -> AsyncIterator[Tuple[str, Dict[str, Any]]]:
        """
        Yield ``(stage_name, stage_result)`` as each pipeline stage completes.

        Consumers can update progress bars or stream partial results to
        MCP clients without waiting for the full pipeline.
        """
        loop = asyncio.get_running_loop()

        # --- Stage 1: Blocking (concurrent strategies) --------------------
        t0 = time.perf_counter()
        blocking_result = await self._run_blocking_concurrent(loop)
        blocking_result["duration_s"] = round(time.perf_counter() - t0, 2)
        yield "blocking", blocking_result
        if self.progress_callback:
            await self.progress_callback("blocking", blocking_result)

        # --- Stage 2: Similarity ------------------------------------------
        t0 = time.perf_counter()
        similarity_result = await loop.run_in_executor(
            self.executor, self._sync_similarity, blocking_result
        )
        similarity_result["duration_s"] = round(time.perf_counter() - t0, 2)
        yield "similarity", similarity_result
        if self.progress_callback:
            await self.progress_callback("similarity", similarity_result)

        # --- Stage 3: Clustering ------------------------------------------
        t0 = time.perf_counter()
        clustering_result = await loop.run_in_executor(
            self.executor, self._sync_clustering
        )
        clustering_result["duration_s"] = round(time.perf_counter() - t0, 2)
        yield "clustering", clustering_result
        if self.progress_callback:
            await self.progress_callback("clustering", clustering_result)

    async def run_blocking_concurrent(
        self, strategies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run multiple blocking strategies concurrently and merge candidates.

        Parameters
        ----------
        strategies:
            List of strategy names to run (e.g. ``["exact", "bm25", "vector"]``).
            Defaults to all strategies configured in the pipeline config.
        """
        loop = asyncio.get_running_loop()
        return await self._run_blocking_concurrent(loop, strategy_names=strategies)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_blocking_concurrent(
        self, loop: asyncio.AbstractEventLoop, strategy_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run configured blocking strategies concurrently via gather."""
        from entity_resolution.strategies import (
            CollectBlockingStrategy,
            BM25BlockingStrategy,
        )

        collection = self.config.collection_name
        fields = self.config.blocking.fields

        # Build list of (strategy_name, callable) pairs
        tasks_to_run = []
        requested = set(strategy_names or [self.config.blocking.strategy])

        if "exact" in requested or "collect" in requested:
            tasks_to_run.append(("exact", lambda: self._run_exact_blocking(collection, fields)))
        if "bm25" in requested or "arangosearch" in requested:
            tasks_to_run.append(("bm25", lambda: self._run_bm25_blocking(collection, fields)))

        if not tasks_to_run:
            # Fall back to whatever the config says
            tasks_to_run.append(
                (self.config.blocking.strategy, lambda: self._run_exact_blocking(collection, fields))
            )

        # Run all strategies concurrently
        futures = [
            loop.run_in_executor(self.executor, fn)
            for _, fn in tasks_to_run
        ]
        results_list = await asyncio.gather(*futures, return_exceptions=True)

        # Merge candidates (deduplicate pairs)
        merged_pairs: set = set()
        strategy_stats: Dict[str, Any] = {}
        for (name, _), result in zip(tasks_to_run, results_list):
            if isinstance(result, Exception):
                logger.warning("Blocking strategy '%s' failed: %s", name, result)
                strategy_stats[name] = {"error": str(result)}
            else:
                pairs = result.get("pairs", [])
                merged_pairs.update(tuple(sorted(p)) for p in pairs)
                strategy_stats[name] = {"pairs_found": len(pairs)}

        return {
            "strategies_run": [name for name, _ in tasks_to_run],
            "strategy_stats": strategy_stats,
            "total_unique_pairs": len(merged_pairs),
            "merged_pairs": list(merged_pairs),
        }

    def _run_exact_blocking(self, collection: str, fields: List[str]) -> Dict[str, Any]:
        from entity_resolution.strategies import CollectBlockingStrategy
        strategy = CollectBlockingStrategy(
            db=self.db,
            collection=collection,
            blocking_fields=fields,
        )
        pairs = strategy.generate_candidates()
        return {"pairs": [[p[0], p[1]] for p in pairs]}

    def _run_bm25_blocking(self, collection: str, fields: List[str]) -> Dict[str, Any]:
        from entity_resolution.strategies import BM25BlockingStrategy
        strategy = BM25BlockingStrategy(
            db=self.db,
            collection=collection,
            search_fields=fields,
        )
        pairs = strategy.generate_candidates()
        return {"pairs": [[p[0], p[1]] for p in pairs]}

    def _sync_similarity(self, blocking_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run similarity computation synchronously (called from executor)."""
        from entity_resolution.services.batch_similarity_service import BatchSimilarityService
        from entity_resolution.services.similarity_edge_service import SimilarityEdgeService
        from entity_resolution.config.er_config import SimilarityConfig

        sim_cfg: SimilarityConfig = self.config.similarity
        pairs = blocking_result.get("merged_pairs", [])
        if not pairs:
            return {"matches_found": 0, "edges_created": 0}

        sim_service = BatchSimilarityService(
            db=self.db,
            collection=self.config.collection_name,
            fields=self.config.blocking.fields,
            threshold=sim_cfg.threshold,
        )
        matches = sim_service.compute_similarity(pairs)

        edge_service = SimilarityEdgeService(
            db=self.db,
            edge_collection=sim_cfg.edge_collection or f"{self.config.collection_name}_similarity_edges",
        )
        edge_service.create_edges(matches)

        return {"matches_found": len(matches), "edges_created": len(matches)}

    def _sync_clustering(self) -> Dict[str, Any]:
        """Run WCC clustering synchronously (called from executor)."""
        from entity_resolution.services.wcc_clustering_service import WCCClusteringService
        from entity_resolution.config.er_config import ClusteringConfig

        clust_cfg: ClusteringConfig = self.config.clustering
        edge_coll = (
            self.config.similarity.edge_collection
            or f"{self.config.collection_name}_similarity_edges"
        )
        svc = WCCClusteringService(db=self.db, edge_collection=edge_coll)
        clusters = svc.find_clusters()

        return {"clusters_found": len(clusters), "total_entities": sum(len(c) for c in clusters)}
