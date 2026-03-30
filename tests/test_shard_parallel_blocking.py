"""Tests for ShardParallelBlockingStrategy."""

import pytest
from unittest.mock import MagicMock, patch

from entity_resolution.strategies.shard_parallel_blocking import (
    ShardParallelBlockingStrategy,
)


class TestShardParallelBlockingStrategy:
    def _make_db(self, pairs=None, num_shards=1, shard_ids=None):
        db = MagicMock()
        cursor = iter(pairs or [])
        db.aql.execute.return_value = cursor

        col_mock = MagicMock()
        col_mock.properties.return_value = {"numberOfShards": num_shards}
        if shard_ids:
            col_mock.shards.return_value = {s: [] for s in shard_ids}
        else:
            col_mock.shards.return_value = {}
        db.collection.return_value = col_mock

        return db

    def test_single_server_no_shard_filtering(self):
        pairs = [
            {"doc1_key": "a", "doc2_key": "b", "blocking_keys": {}, "block_size": 2, "shard_id": "single"},
        ]
        db = self._make_db(pairs=pairs, num_shards=1)
        strategy = ShardParallelBlockingStrategy(
            db=db, collection="test", blocking_fields=["phone", "state"]
        )
        result = strategy.generate_candidates()
        assert len(result) == 1
        db.aql.execute.assert_called_once()

    def test_get_shard_ids_single_server(self):
        db = self._make_db(num_shards=1)
        strategy = ShardParallelBlockingStrategy(
            db=db, collection="test", blocking_fields=["phone"]
        )
        ids = strategy._get_shard_ids()
        assert ids == [""]

    def test_get_shard_ids_cluster(self):
        db = self._make_db(num_shards=3, shard_ids=["s1", "s2", "s3"])
        strategy = ShardParallelBlockingStrategy(
            db=db, collection="test", blocking_fields=["phone"]
        )
        ids = strategy._get_shard_ids()
        assert len(ids) == 3
        assert set(ids) == {"s1", "s2", "s3"}

    def test_statistics_populated(self):
        db = self._make_db(num_shards=1)
        strategy = ShardParallelBlockingStrategy(
            db=db, collection="test", blocking_fields=["phone", "state"]
        )
        strategy.generate_candidates()
        stats = strategy.get_statistics()
        assert stats["shard_count"] == 1
        assert stats["blocking_fields"] == ["phone", "state"]
        assert "execution_time_seconds" in stats

    def test_normalizes_and_deduplicates(self):
        pairs = [
            {"doc1_key": "b", "doc2_key": "a", "blocking_keys": {}, "block_size": 2, "shard_id": "s"},
            {"doc1_key": "a", "doc2_key": "b", "blocking_keys": {}, "block_size": 2, "shard_id": "s"},
        ]
        db = self._make_db(pairs=pairs, num_shards=1)
        strategy = ShardParallelBlockingStrategy(
            db=db, collection="test", blocking_fields=["phone"]
        )
        result = strategy.generate_candidates()
        assert len(result) == 1
        assert result[0]["doc1_key"] == "a"
        assert result[0]["doc2_key"] == "b"
