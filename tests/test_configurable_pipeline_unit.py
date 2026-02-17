from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline


@dataclass
class _BlockingCfg:
    max_block_size: int = 100


@dataclass
class _SimilarityCfg:
    batch_size: int = 100


@dataclass
class _ClusteringCfg:
    store_results: bool = True
    min_cluster_size: int = 2


class _FakeConfig:
    def __init__(self, entity_type: str = "company", store_clusters: bool = True):
        self.entity_type = entity_type
        self.collection_name = "customers"
        self.edge_collection = "similarTo"
        self.blocking = _BlockingCfg()
        self.similarity = _SimilarityCfg()
        self.clustering = _ClusteringCfg(store_results=store_clusters)
        self.edges = object()

    def validate(self):
        return []


class _FakeDB:
    pass


def test_init_requires_config_or_path() -> None:
    with pytest.raises(ValueError):
        ConfigurableERPipeline(db=_FakeDB(), config=None, config_path=None)


def test_init_loads_json_or_yaml_via_erpipelineconfig(monkeypatch, tmp_path: Path) -> None:
    from entity_resolution.core import configurable_pipeline as mod

    cfg = _FakeConfig()
    monkeypatch.setattr(mod.ERPipelineConfig, "from_json", lambda p: cfg)
    monkeypatch.setattr(mod.ERPipelineConfig, "from_yaml", lambda p: cfg)

    p_json = tmp_path / "cfg.json"
    p_json.write_text("{}")
    p_yaml = tmp_path / "cfg.yaml"
    p_yaml.write_text("x: y")

    pipe1 = ConfigurableERPipeline(db=_FakeDB(), config=None, config_path=p_json)
    assert pipe1.config is cfg

    pipe2 = ConfigurableERPipeline(db=_FakeDB(), config=None, config_path=p_yaml)
    assert pipe2.config is cfg


def test_run_routes_to_address_pipeline(monkeypatch) -> None:
    cfg = _FakeConfig(entity_type="address")
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)
    monkeypatch.setattr(pipe, "_run_address_er", lambda results, start_time: {"address": True})
    out = pipe.run()
    assert out == {"address": True}


def test_run_standard_pipeline_happy_path(monkeypatch) -> None:
    cfg = _FakeConfig(entity_type="company", store_clusters=True)
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    monkeypatch.setattr(pipe, "_run_blocking", lambda: [{"a": 1}, {"a": 2}])
    monkeypatch.setattr(pipe, "_run_similarity", lambda pairs: [{"m": 1}])
    monkeypatch.setattr(pipe, "_run_edge_creation", lambda matches: 7)
    monkeypatch.setattr(pipe, "_run_clustering", lambda: [["1", "2"]])

    out = pipe.run()
    assert out["blocking"]["candidate_pairs"] == 2
    assert out["similarity"]["matches_found"] == 1
    assert out["edges"]["edges_created"] == 7
    assert out["clustering"]["clusters_found"] == 1
    assert out["total_runtime_seconds"] >= 0.0


def test_run_standard_pipeline_handles_no_candidates(monkeypatch) -> None:
    cfg = _FakeConfig(entity_type="company", store_clusters=False)
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    monkeypatch.setattr(pipe, "_run_blocking", lambda: [])
    out = pipe.run()
    assert out["blocking"]["candidate_pairs"] == 0
    assert out["similarity"]["matches_found"] == 0
    assert out["edges"]["edges_created"] == 0
    assert out["clustering"]["clusters_found"] == 0

