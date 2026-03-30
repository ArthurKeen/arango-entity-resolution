"""
Shard-parallel blocking strategy.

Distributes blocking work across ArangoDB shards for cluster deployments,
enabling parallel candidate generation on sharded collections.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from arango.database import StandardDatabase

from .base_strategy import BlockingStrategy

logger = logging.getLogger(__name__)


class ShardParallelBlockingStrategy(BlockingStrategy):
    """Distribute blocking across ArangoDB shards for parallel execution.

    On a sharded ArangoDB cluster, this strategy queries each shard
    independently using ``OPTIONS {shardIds: [...]}`` and merges results.
    For single-server deployments, it falls back to a single-shard run.

    Parameters
    ----------
    db:
        ArangoDB database connection.
    collection:
        Source collection name.
    blocking_fields:
        Fields to use as composite blocking key.
    max_block_size:
        Maximum block size before skipping (default 100).
    min_block_size:
        Minimum block size to generate pairs (default 2).
    parallelism:
        Number of concurrent shard queries (default 4).
    filters:
        Optional field filters (same format as base class).
    """

    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        blocking_fields: List[str],
        max_block_size: int = 100,
        min_block_size: int = 2,
        parallelism: int = 4,
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(db, collection, filters)
        self.blocking_fields = blocking_fields
        self.max_block_size = max_block_size
        self.min_block_size = min_block_size
        self.parallelism = parallelism

    def _get_shard_ids(self) -> List[str]:
        """Retrieve shard IDs for the collection.

        Returns a list with a single empty string for single-server
        deployments (no shard filtering needed).
        """
        try:
            col = self.db.collection(self.collection)
            props = col.properties()
            num_shards = props.get("numberOfShards", 1)
            if num_shards <= 1:
                return [""]

            shards_info = col.shards()
            if isinstance(shards_info, dict):
                return list(shards_info.keys())
            return [""]
        except Exception:
            logger.debug("Could not retrieve shard info; running single-shard")
            return [""]

    def _blocking_query_for_shard(self, shard_id: str) -> List[Dict[str, Any]]:
        """Run COLLECT-based blocking on a single shard."""
        collect_fields = ", ".join(
            f"f{i} = d.`{field}`" for i, field in enumerate(self.blocking_fields)
        )
        group_key_parts = ", ".join(f"f{i}" for i in range(len(self.blocking_fields)))

        filter_conditions, filter_binds = self._build_filter_conditions(self.filters)
        filter_clause = ""
        if filter_conditions:
            filter_clause = "FILTER " + " AND ".join(filter_conditions)

        shard_option = ""
        if shard_id:
            shard_option = f"OPTIONS {{shardIds: [@shard_id]}}"
            filter_binds["shard_id"] = shard_id

        query = f"""
        FOR d IN @@collection {shard_option}
            {filter_clause}
            COLLECT {collect_fields} INTO group
            LET block_size = LENGTH(group)
            FILTER block_size >= @min_block AND block_size <= @max_block
            FOR i IN 0..block_size-2
                FOR j IN i+1..block_size-1
                    RETURN {{
                        doc1_key: group[i].d._key,
                        doc2_key: group[j].d._key,
                        blocking_keys: {{{group_key_parts}}},
                        block_size: block_size,
                        shard_id: @shard_id_label
                    }}
        """

        bind_vars = {
            "@collection": self.collection,
            "min_block": self.min_block_size,
            "max_block": self.max_block_size,
            "shard_id_label": shard_id or "single",
            **filter_binds,
        }

        cursor = self.db.aql.execute(query, bind_vars=bind_vars)
        return list(cursor)

    def generate_candidates(self) -> List[Dict[str, Any]]:
        """Generate candidates in parallel across shards."""
        start = time.time()
        shard_ids = self._get_shard_ids()

        all_pairs: List[Dict[str, Any]] = []

        if len(shard_ids) <= 1:
            pairs = self._blocking_query_for_shard(shard_ids[0] if shard_ids else "")
            all_pairs.extend(pairs)
        else:
            with ThreadPoolExecutor(max_workers=self.parallelism) as executor:
                futures = {
                    executor.submit(self._blocking_query_for_shard, sid): sid
                    for sid in shard_ids
                }
                for future in as_completed(futures):
                    sid = futures[future]
                    try:
                        pairs = future.result()
                        all_pairs.extend(pairs)
                        logger.info("Shard %s produced %d pairs", sid, len(pairs))
                    except Exception as exc:
                        logger.error("Shard %s failed: %s", sid, exc)

        normalized = self._normalize_pairs(all_pairs)
        elapsed = time.time() - start
        self._update_statistics(normalized, elapsed)

        self._stats.update({
            "shard_count": len(shard_ids),
            "parallelism": self.parallelism,
            "blocking_fields": self.blocking_fields,
        })

        logger.info(
            "Shard-parallel blocking: %d pairs from %d shards in %.2fs",
            len(normalized), len(shard_ids), elapsed,
        )
        return normalized
