"""
Multi-strategy blocking orchestrator.

Runs multiple blocking strategies in sequence and merges/deduplicates
candidate pairs. This allows combining strategies with different strengths
(e.g. exact key blocking + fuzzy BM25 + semantic vector search) into a
single candidate set with provenance tracking.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Literal, Optional, Sequence

from ..strategies.base_strategy import BlockingStrategy

logger = logging.getLogger(__name__)

MergeMode = Literal["union", "intersection"]


class MultiStrategyOrchestrator:
    """Run multiple blocking strategies and merge their candidate pairs.

    Parameters
    ----------
    strategies:
        Ordered sequence of :class:`BlockingStrategy` instances to execute.
    merge_mode:
        How to combine candidate pairs across strategies.

        * ``"union"`` (default) — return all unique pairs found by *any*
          strategy.  Best for recall.
        * ``"intersection"`` — return only pairs found by *every* strategy.
          Best for precision.
    deduplicate:
        When True (default), candidate pairs are deduplicated by
        ``(doc1_key, doc2_key)`` after merging.

    Example
    -------
    ::

        orchestrator = MultiStrategyOrchestrator(
            strategies=[collect_strategy, bm25_strategy, vector_strategy],
            merge_mode="union",
        )
        candidates = orchestrator.run()
        stats = orchestrator.get_statistics()
    """

    def __init__(
        self,
        strategies: Sequence[BlockingStrategy],
        merge_mode: MergeMode = "union",
        deduplicate: bool = True,
    ) -> None:
        if not strategies:
            raise ValueError("At least one blocking strategy is required")
        if merge_mode not in ("union", "intersection"):
            raise ValueError(f"merge_mode must be 'union' or 'intersection', got '{merge_mode}'")

        self.strategies = list(strategies)
        self.merge_mode = merge_mode
        self.deduplicate = deduplicate
        self._stats: Dict[str, Any] = {}

    def run(self) -> List[Dict[str, Any]]:
        """Execute all strategies and merge results.

        Returns
        -------
        list[dict]
            Merged (and optionally deduplicated) candidate pairs.  Each pair
            carries an extra ``"sources"`` field listing which strategy names
            produced it.
        """
        start = time.time()
        per_strategy_pairs: List[List[Dict[str, Any]]] = []
        strategy_stats: List[Dict[str, Any]] = []

        for strategy in self.strategies:
            name = strategy.__class__.__name__
            logger.info("Running blocking strategy: %s", name)
            s_start = time.time()
            pairs = strategy.generate_candidates()
            s_elapsed = time.time() - s_start
            per_strategy_pairs.append(pairs)

            stats = strategy.get_statistics()
            stats["strategy_name"] = name
            stats["execution_time_seconds"] = round(s_elapsed, 3)
            stats["candidate_count"] = len(pairs)
            strategy_stats.append(stats)
            logger.info(
                "  %s produced %d candidates in %.2fs",
                name,
                len(pairs),
                s_elapsed,
            )

        if self.merge_mode == "union":
            merged = self._merge_union(per_strategy_pairs)
        else:
            merged = self._merge_intersection(per_strategy_pairs)

        if self.deduplicate:
            merged = self._deduplicate(merged)

        elapsed = time.time() - start
        self._stats = {
            "merge_mode": self.merge_mode,
            "deduplicate": self.deduplicate,
            "total_strategies": len(self.strategies),
            "total_candidates": len(merged),
            "execution_time_seconds": round(elapsed, 3),
            "per_strategy": strategy_stats,
        }
        logger.info(
            "Orchestrator finished: %d total candidates from %d strategies in %.2fs",
            len(merged),
            len(self.strategies),
            elapsed,
        )
        return merged

    def get_statistics(self) -> Dict[str, Any]:
        """Return statistics from the most recent :meth:`run` call."""
        return self._stats.copy()

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pair_key(pair: Dict[str, Any]) -> tuple:
        k1 = pair.get("doc1_key", "")
        k2 = pair.get("doc2_key", "")
        return (min(k1, k2), max(k1, k2))

    def _merge_union(
        self,
        per_strategy: List[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        seen: Dict[tuple, Dict[str, Any]] = {}
        for idx, pairs in enumerate(per_strategy):
            name = self.strategies[idx].__class__.__name__
            for pair in pairs:
                key = self._pair_key(pair)
                if key in seen:
                    seen[key].setdefault("sources", [])
                    if name not in seen[key]["sources"]:
                        seen[key]["sources"].append(name)
                else:
                    entry = pair.copy()
                    entry["sources"] = [name]
                    seen[key] = entry
        return list(seen.values())

    def _merge_intersection(
        self,
        per_strategy: List[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        if not per_strategy:
            return []

        key_sets = []
        pair_map: Dict[tuple, Dict[str, Any]] = {}
        for idx, pairs in enumerate(per_strategy):
            name = self.strategies[idx].__class__.__name__
            keys = set()
            for pair in pairs:
                key = self._pair_key(pair)
                keys.add(key)
                if key not in pair_map:
                    entry = pair.copy()
                    entry["sources"] = [name]
                    pair_map[key] = entry
                else:
                    if name not in pair_map[key].get("sources", []):
                        pair_map[key].setdefault("sources", []).append(name)
            key_sets.append(keys)

        common = key_sets[0]
        for ks in key_sets[1:]:
            common = common & ks

        return [pair_map[k] for k in common if k in pair_map]

    @staticmethod
    def _deduplicate(pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for pair in pairs:
            k1 = pair.get("doc1_key", "")
            k2 = pair.get("doc2_key", "")
            key = (min(k1, k2), max(k1, k2))
            if key not in seen:
                seen.add(key)
                unique.append(pair)
        return unique

    @classmethod
    def from_config(
        cls,
        db: "StandardDatabase",
        config: Dict[str, Any],
    ) -> "MultiStrategyOrchestrator":
        """Build an orchestrator from a YAML/dict configuration.

        Expected format::

            orchestrator:
              merge_mode: union
              deduplicate: true
              strategies:
                - type: collect
                  blocking_fields: [phone, state]
                  max_block_size: 50
                - type: bm25
                  search_field: company_name
                  view_name: companies_view

        Parameters
        ----------
        db:
            ArangoDB database connection.
        config:
            Dict parsed from YAML.

        Returns
        -------
        MultiStrategyOrchestrator
        """
        from ..strategies.collect_blocking import CollectBlockingStrategy
        from ..strategies.bm25_blocking import BM25BlockingStrategy

        strategy_builders = {
            "collect": lambda cfg: CollectBlockingStrategy(
                db=db,
                collection=cfg["collection"],
                blocking_fields=cfg["blocking_fields"],
                filters=cfg.get("filters"),
                max_block_size=cfg.get("max_block_size", 100),
                min_block_size=cfg.get("min_block_size", 2),
            ),
            "bm25": lambda cfg: BM25BlockingStrategy(
                db=db,
                collection=cfg["collection"],
                search_field=cfg["search_field"],
                view_name=cfg.get("view_name"),
                top_n=cfg.get("top_n", 10),
                score_threshold=cfg.get("score_threshold", 0.0),
            ),
        }

        strategies: List[BlockingStrategy] = []
        for entry in config.get("strategies", []):
            stype = entry.get("type", "")
            builder = strategy_builders.get(stype)
            if builder is None:
                raise ValueError(
                    f"Unknown strategy type '{stype}'. "
                    f"Valid types: {list(strategy_builders.keys())}"
                )
            strategies.append(builder(entry))

        return cls(
            strategies=strategies,
            merge_mode=config.get("merge_mode", "union"),
            deduplicate=config.get("deduplicate", True),
        )
