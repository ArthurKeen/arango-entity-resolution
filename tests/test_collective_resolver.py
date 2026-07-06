"""Unit tests for CollectiveResolver + CollectiveConfig (plan 3.2)."""

from __future__ import annotations

from entity_resolution.config.er_config import CollectiveConfig, ERPipelineConfig
from entity_resolution.core.collective_resolver import (
    CollectiveResolver,
    connected_components,
)


def test_connected_components():
    comps = connected_components([("A", "B"), ("B", "C"), ("X", "Y")])
    as_sets = sorted(sorted(c) for c in comps)
    assert ["A", "B", "C"] in as_sets
    assert ["X", "Y"] in as_sets


def test_reaches_fixpoint():
    # Scoring ignores the cache => clustering is stable after round 1.
    def score(pairs, cache):
        return [(a, b, 0.9) for a, b in pairs]

    r = CollectiveResolver(
        score_pairs=score, cluster=connected_components,
        base_neighbor_cache={}, threshold=0.5, max_rounds=5,
    ).resolve([("A", "B")])
    assert r["converged"] is True
    assert r["rounds"] == 2  # round 1 forms it, round 2 confirms no change
    assert r["clusters"] == [["A", "B"]]


def test_collective_lift_transfers_relationship():
    # A has no employer; B/C/D all work at Acme. A~B by name only. After A~B
    # merge, A inherits Acme => A~C and A~D fire on the shared employer.
    base = {"A": set(), "B": {"Acme"}, "C": {"Acme"}, "D": {"Acme"}}
    attr = {("A", "B"): 0.9}

    def score(pairs, cache):
        out = []
        for a, b in pairs:
            name = attr.get((a, b), attr.get((b, a), 0.0))
            shared = 1.0 if (cache.get(a, set()) & cache.get(b, set())) else 0.0
            out.append((a, b, max(name, shared)))
        return out

    pairs = [("A", "B"), ("A", "C"), ("A", "D")]

    single = CollectiveResolver(
        score_pairs=score, cluster=connected_components,
        base_neighbor_cache=base, threshold=0.7, max_rounds=1,
    ).resolve(pairs)
    assert single["clusters"] == [["A", "B"]]  # single pass misses C, D

    collective = CollectiveResolver(
        score_pairs=score, cluster=connected_components,
        base_neighbor_cache=base, threshold=0.7, max_rounds=5,
    ).resolve(pairs)
    assert collective["converged"] is True
    assert collective["clusters"] == [["A", "B", "C", "D"]]  # merge propagated
    assert collective["rounds"] >= 2


def test_max_rounds_cap_without_convergence():
    calls = {"i": 0}

    def score(pairs, cache):
        i = calls["i"]
        calls["i"] += 1
        return [("A", f"n{i}", 1.0)]  # a new distinct edge every round

    r = CollectiveResolver(
        score_pairs=score, cluster=connected_components,
        base_neighbor_cache={}, threshold=0.5, max_rounds=4,
    ).resolve([("A", "B")])
    assert r["rounds"] == 4
    assert r["converged"] is False
    assert r["oscillated"] is False


def test_oscillation_guard():
    states = [[("A", "B")], [("A", "C")], [("A", "B")], [("A", "C")]]
    calls = {"i": 0}

    def score(pairs, cache):
        edges = states[min(calls["i"], len(states) - 1)]
        calls["i"] += 1
        return [(a, b, 1.0) for a, b in edges]

    r = CollectiveResolver(
        score_pairs=score, cluster=connected_components,
        base_neighbor_cache={}, threshold=0.5, max_rounds=10,
    ).resolve([("A", "B"), ("A", "C")])
    assert r["oscillated"] is True
    assert r["converged"] is False


# --- config ---

def test_collective_config_from_dict_and_validate():
    cfg = CollectiveConfig.from_dict({"enabled": True, "max_rounds": 3})
    assert cfg.enabled and cfg.max_rounds == 3
    assert cfg.validate() == []
    bad = CollectiveConfig(enabled=True, max_rounds=99)
    assert any("max_rounds" in e for e in bad.validate())


def test_pipeline_config_parses_collective():
    cfg = ERPipelineConfig.from_dict(
        {"entity_resolution": {
            "entity_type": "company", "collection_name": "orgs",
            "collective": {"enabled": True, "max_rounds": 4},
        }}
    )
    assert cfg.collective.enabled and cfg.collective.max_rounds == 4
    assert cfg.validate() == [] or all("collective" not in e for e in cfg.validate())
    assert cfg.to_dict()["entity_resolution"]["collective"]["max_rounds"] == 4
