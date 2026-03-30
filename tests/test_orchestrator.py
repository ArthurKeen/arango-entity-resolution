"""Tests for MultiStrategyOrchestrator."""

import pytest
from unittest.mock import MagicMock

from entity_resolution.core.orchestrator import MultiStrategyOrchestrator


def _make_strategy(name: str, pairs):
    """Create a mock blocking strategy that returns given pairs."""
    strategy = MagicMock()
    strategy.__class__ = type(name, (), {})
    strategy.__class__.__name__ = name
    strategy.generate_candidates.return_value = pairs
    strategy.get_statistics.return_value = {"total_pairs": len(pairs)}
    return strategy


class TestMultiStrategyOrchestrator:
    def test_requires_at_least_one_strategy(self):
        with pytest.raises(ValueError, match="At least one"):
            MultiStrategyOrchestrator(strategies=[])

    def test_rejects_invalid_merge_mode(self):
        s = _make_strategy("S1", [])
        with pytest.raises(ValueError, match="merge_mode"):
            MultiStrategyOrchestrator(strategies=[s], merge_mode="bad")

    def test_union_merge_single_strategy(self):
        pairs = [
            {"doc1_key": "a", "doc2_key": "b"},
            {"doc1_key": "c", "doc2_key": "d"},
        ]
        s = _make_strategy("Collect", pairs)
        orch = MultiStrategyOrchestrator(strategies=[s], merge_mode="union")
        result = orch.run()
        assert len(result) == 2
        assert all("sources" in p for p in result)
        assert result[0]["sources"] == ["Collect"]

    def test_union_merge_deduplicates_across_strategies(self):
        pairs1 = [
            {"doc1_key": "a", "doc2_key": "b"},
            {"doc1_key": "c", "doc2_key": "d"},
        ]
        pairs2 = [
            {"doc1_key": "b", "doc2_key": "a"},  # same pair reversed
            {"doc1_key": "e", "doc2_key": "f"},
        ]
        s1 = _make_strategy("Collect", pairs1)
        s2 = _make_strategy("BM25", pairs2)
        orch = MultiStrategyOrchestrator(strategies=[s1, s2], merge_mode="union")
        result = orch.run()
        assert len(result) == 3
        ab_pair = next(p for p in result if set([p["doc1_key"], p["doc2_key"]]) == {"a", "b"})
        assert sorted(ab_pair["sources"]) == ["BM25", "Collect"]

    def test_intersection_merge(self):
        pairs1 = [
            {"doc1_key": "a", "doc2_key": "b"},
            {"doc1_key": "c", "doc2_key": "d"},
        ]
        pairs2 = [
            {"doc1_key": "a", "doc2_key": "b"},
            {"doc1_key": "e", "doc2_key": "f"},
        ]
        s1 = _make_strategy("Collect", pairs1)
        s2 = _make_strategy("BM25", pairs2)
        orch = MultiStrategyOrchestrator(strategies=[s1, s2], merge_mode="intersection")
        result = orch.run()
        assert len(result) == 1
        assert result[0]["doc1_key"] == "a"
        assert result[0]["doc2_key"] == "b"

    def test_intersection_with_reversed_keys(self):
        pairs1 = [{"doc1_key": "a", "doc2_key": "b"}]
        pairs2 = [{"doc1_key": "b", "doc2_key": "a"}]
        s1 = _make_strategy("S1", pairs1)
        s2 = _make_strategy("S2", pairs2)
        orch = MultiStrategyOrchestrator(strategies=[s1, s2], merge_mode="intersection")
        result = orch.run()
        assert len(result) == 1

    def test_statistics_populated_after_run(self):
        s = _make_strategy("S1", [{"doc1_key": "a", "doc2_key": "b"}])
        orch = MultiStrategyOrchestrator(strategies=[s])
        orch.run()
        stats = orch.get_statistics()
        assert stats["total_strategies"] == 1
        assert stats["total_candidates"] == 1
        assert stats["merge_mode"] == "union"
        assert len(stats["per_strategy"]) == 1
        assert stats["per_strategy"][0]["candidate_count"] == 1

    def test_deduplicate_false_preserves_reversed_duplicates(self):
        pairs1 = [{"doc1_key": "a", "doc2_key": "b"}]
        pairs2 = [{"doc1_key": "b", "doc2_key": "a"}]
        s1 = _make_strategy("S1", pairs1)
        s2 = _make_strategy("S2", pairs2)
        orch = MultiStrategyOrchestrator(strategies=[s1, s2], deduplicate=True)
        result = orch.run()
        assert len(result) == 1

    def test_empty_strategies_produce_empty_results(self):
        s1 = _make_strategy("S1", [])
        s2 = _make_strategy("S2", [])
        orch = MultiStrategyOrchestrator(strategies=[s1, s2])
        result = orch.run()
        assert result == []

    def test_sources_tracks_multiple_strategy_names(self):
        pair = {"doc1_key": "x", "doc2_key": "y"}
        s1 = _make_strategy("Alpha", [pair])
        s2 = _make_strategy("Beta", [pair])
        s3 = _make_strategy("Gamma", [pair])
        orch = MultiStrategyOrchestrator(strategies=[s1, s2, s3])
        result = orch.run()
        assert len(result) == 1
        assert sorted(result[0]["sources"]) == ["Alpha", "Beta", "Gamma"]
