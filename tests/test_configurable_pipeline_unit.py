from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import pytest

from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline


@dataclass
class _BlockingCfg:
    max_block_size: int = 100
    min_block_size: int = 2
    strategy: str = "exact"
    fields: list = field(default_factory=list)
    search_field: Optional[str] = None
    blocking_field: Optional[str] = None
    embedding_field: Optional[str] = None
    similarity_threshold: float = 0.75
    limit_per_entity: int = 20
    num_hash_tables: int = 10
    num_hyperplanes: int = 8
    random_seed: Optional[int] = 42

    def parse_fields(self) -> tuple:
        """Minimal implementation matching BlockingConfig.parse_fields() contract."""
        field_names: list = []
        computed_fields: dict = {}
        for item in (self.fields or []):
            if isinstance(item, str):
                name = item.strip()
            elif isinstance(item, dict):
                name = (item.get("name") or item.get("field") or "").strip()
            else:
                continue
            if name:
                field_names.append(name)
        seen: set = set()
        deduped = [f for f in field_names if not (f in seen or seen.add(f))]
        return deduped, computed_fields


@dataclass
class _SimilarityCfg:
    batch_size: int = 100
    threshold: float = 0.75
    algorithm: str = "jaro_winkler"
    field_weights: dict = field(default_factory=dict)
    transformers: dict = field(default_factory=dict)


@dataclass
class _ActiveLearningCfg:
    enabled: bool = False
    feedback_collection: Optional[str] = None
    refresh_every: int = 100
    model: Optional[str] = None
    low_threshold: float = 0.55
    high_threshold: float = 0.80
    optimizer_target_precision: float = 0.95
    optimizer_min_samples: int = 20


@dataclass
class _ClusteringCfg:
    store_results: bool = True
    min_cluster_size: int = 2


@dataclass
class _EmbeddingCfg:
    model_name: str = "all-MiniLM-L6-v2"
    runtime: str = "pytorch"
    device: str = "cpu"
    provider: str = "cpu"
    provider_options: dict[str, Any] = field(default_factory=dict)
    onnx_model_path: Optional[str] = None
    startup_mode: str = "permissive"
    coreml_use_basic_optimizations: bool = True
    coreml_warmup_runs: int = 10
    coreml_max_p95_latency_ms: float = 65.0
    coreml_warmup_batch_size: int = 8
    coreml_warmup_seq_len: int = 128
    embedding_field: str = "embedding_vector"
    multi_resolution_mode: bool = False
    coarse_model_name: Optional[str] = None
    fine_model_name: Optional[str] = None
    embedding_field_coarse: str = "embedding_vector_coarse"
    embedding_field_fine: str = "embedding_vector_fine"
    profile: str = "default"
    batch_size: int = 32


class _FakeConfig:
    def __init__(self, entity_type: str = "company", store_clusters: bool = True,
                 blocking: Optional[_BlockingCfg] = None,
                 active_learning: Optional[_ActiveLearningCfg] = None,
                 embedding: Optional[_EmbeddingCfg] = None):
        self.entity_type = entity_type
        self.collection_name = "customers"
        self.edge_collection = "similarTo"
        self.blocking = blocking if blocking is not None else _BlockingCfg()
        self.similarity = _SimilarityCfg()
        self.clustering = _ClusteringCfg(store_results=store_clusters)
        self.active_learning = active_learning if active_learning is not None else _ActiveLearningCfg()
        self.embedding = embedding
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

    monkeypatch.setattr(pipe, "run_blocking", lambda: [{"a": 1}, {"a": 2}])
    monkeypatch.setattr(pipe, "run_similarity", lambda pairs: [{"m": 1}])
    monkeypatch.setattr(pipe, "run_edge_creation", lambda matches: 7)
    monkeypatch.setattr(pipe, "run_clustering", lambda: [["1", "2"]])

    out = pipe.run()
    assert out["blocking"]["candidate_pairs"] == 2
    assert out["similarity"]["matches_found"] == 1
    assert out["edges"]["edges_created"] == 7
    assert out["clustering"]["clusters_found"] == 1
    assert out["total_runtime_seconds"] >= 0.0
    assert out["embedding"]["enabled"] is False


def test_run_standard_pipeline_handles_no_candidates(monkeypatch) -> None:
    cfg = _FakeConfig(entity_type="company", store_clusters=False)
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    monkeypatch.setattr(pipe, "run_blocking", lambda: [])
    out = pipe.run()
    assert out["blocking"]["candidate_pairs"] == 0
    assert out["similarity"]["matches_found"] == 0
    assert out["edges"]["edges_created"] == 0
    assert out["clustering"]["clusters_found"] == 0
    assert out["embedding"]["enabled"] is False


def test_setup_embedding_runtime_pytorch(monkeypatch) -> None:
    cfg = _FakeConfig(
        embedding=_EmbeddingCfg(runtime="pytorch", device="auto", provider="cpu")
    )
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    class _FakeEmbeddingService:
        def __init__(self, **kwargs):
            assert kwargs["runtime"] == "pytorch"
            assert kwargs["device"] == "auto"
            self.device = "mps"
            self.resolved_provider = "pytorch"

        def get_runtime_health(self):
            return {"ok": True, "resolved_device": "mps"}

    import entity_resolution.core.configurable_pipeline as mod
    monkeypatch.setattr(mod, "EmbeddingService", _FakeEmbeddingService)

    out = pipe._setup_embedding_runtime()
    assert out["enabled"] is True
    assert out["runtime"] == "pytorch"
    assert out["requested_device"] == "auto"
    assert out["resolved_device"] == "mps"
    assert out["resolved_provider"] == "pytorch"
    assert out["health"]["ok"] is True


def test_setup_embedding_runtime_onnxruntime(monkeypatch) -> None:
    cfg = _FakeConfig(
        embedding=_EmbeddingCfg(
            runtime="onnxruntime",
            provider="auto",
            onnx_model_path="/tmp/model.onnx",
        )
    )
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    class _FakeOnnxBackend:
        def __init__(self, **kwargs):
            assert kwargs["model_path"] == "/tmp/model.onnx"
            assert kwargs["coreml_use_basic_optimizations"] is True
            assert kwargs["coreml_warmup_runs"] == 10
            self.resolved_provider = "coreml"
            self.fallback_count = 0
            self.last_fallback_reason = None
            self.last_warmup_p95_latency_ms = 12.3
            self.session_optimization_level = "ORT_ENABLE_BASIC"

        def load_model(self):
            return None

        def health(self):
            return {"ok": True, "provider": "coreml"}

    import entity_resolution.core.configurable_pipeline as mod
    monkeypatch.setattr(mod, "OnnxRuntimeEmbeddingBackend", _FakeOnnxBackend)

    out = pipe._setup_embedding_runtime()
    assert out["enabled"] is True
    assert out["runtime"] == "onnxruntime"
    assert out["requested_provider"] == "auto"
    assert out["resolved_provider"] == "coreml"
    assert out["health"]["ok"] is True
    assert out["telemetry"]["provider_used"] == "coreml"


def test_run_includes_embedding_phase_when_configured(monkeypatch) -> None:
    cfg = _FakeConfig(embedding=_EmbeddingCfg(runtime="pytorch"))
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    monkeypatch.setattr(
        pipe,
        "_setup_embedding_runtime",
        lambda: {
            "enabled": True,
            "runtime": "pytorch",
            "resolved_provider": "pytorch",
            "health": {"ok": True},
        },
    )
    monkeypatch.setattr(pipe, "run_blocking", lambda: [])

    out = pipe.run()
    assert out["embedding"]["enabled"] is True
    assert out["embedding"]["runtime"] == "pytorch"
    assert out["embedding"]["runtime_seconds"] >= 0.0
    assert out["embedding"]["setup_latency_ms"] >= 0.0
    assert out["embedding"]["health"]["ok"] is True


def test_get_embedding_runtime_health_when_disabled() -> None:
    cfg = _FakeConfig(embedding=None)
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)
    out = pipe.get_embedding_runtime_health()
    assert out["enabled"] is False


def test_get_embedding_runtime_health_uses_setup(monkeypatch) -> None:
    cfg = _FakeConfig(embedding=_EmbeddingCfg(runtime="pytorch"))
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)
    monkeypatch.setattr(
        pipe,
        "_setup_embedding_runtime",
        lambda: {
            "enabled": True,
            "runtime": "pytorch",
            "model_name": "all-MiniLM-L6-v2",
            "requested_device": "auto",
            "resolved_device": "mps",
            "requested_provider": "cpu",
            "resolved_provider": "pytorch",
            "health": {"ok": True},
        },
    )
    out = pipe.get_embedding_runtime_health()
    assert out["enabled"] is True
    assert out["health"]["ok"] is True


def test_setup_embedding_runtime_strict_pytorch_cuda_unavailable_raises(monkeypatch) -> None:
    cfg = _FakeConfig(
        embedding=_EmbeddingCfg(runtime="pytorch", device="cuda", startup_mode="strict")
    )
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    class _FakeEmbeddingService:
        def __init__(self, **kwargs):
            self.device = "cuda"
            self.resolved_provider = "pytorch"

        def get_runtime_health(self):
            return {
                "ok": True,
                "cuda_available": False,
                "mps_available": False,
            }

    import entity_resolution.core.configurable_pipeline as mod
    monkeypatch.setattr(mod, "EmbeddingService", _FakeEmbeddingService)

    with pytest.raises(RuntimeError, match="requested device 'cuda'"):
        pipe._setup_embedding_runtime()


def test_setup_embedding_runtime_strict_onnx_missing_provider_raises(monkeypatch) -> None:
    cfg = _FakeConfig(
        embedding=_EmbeddingCfg(
            runtime="onnxruntime",
            provider="coreml",
            onnx_model_path="/tmp/model.onnx",
            startup_mode="strict",
        )
    )
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    class _FakeOnnxBackend:
        def __init__(self, **kwargs):
            self.resolved_provider = "coreml"
            self.fallback_count = 1
            self.last_fallback_reason = "requested provider unavailable"
            self.last_warmup_p95_latency_ms = 88.8
            self.session_optimization_level = "ORT_ENABLE_BASIC"

        def load_model(self):
            return None

        def health(self):
            return {
                "ok": True,
                "available_ort_providers": ["CPUExecutionProvider"],
            }

    import entity_resolution.core.configurable_pipeline as mod
    monkeypatch.setattr(mod, "OnnxRuntimeEmbeddingBackend", _FakeOnnxBackend)

    with pytest.raises(RuntimeError, match="requested provider 'coreml'"):
        pipe._setup_embedding_runtime()


def test_get_embedding_runtime_health_startup_mode_override(monkeypatch) -> None:
    cfg = _FakeConfig(embedding=_EmbeddingCfg(runtime="pytorch", startup_mode="permissive"))
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    observed_modes = []

    def _fake_setup():
        observed_modes.append(pipe.config.embedding.startup_mode)
        return {"enabled": True, "runtime": "pytorch", "health": {"ok": True}}

    monkeypatch.setattr(pipe, "_setup_embedding_runtime", _fake_setup)
    pipe.get_embedding_runtime_health(startup_mode="strict")
    assert observed_modes == ["strict"]
    assert pipe.config.embedding.startup_mode == "permissive"


def test_run_similarity_with_active_learning_overrides_uncertain_scores(monkeypatch) -> None:
    cfg = _FakeConfig(
        active_learning=_ActiveLearningCfg(enabled=True, refresh_every=5, low_threshold=0.55, high_threshold=0.80)
    )
    cfg.similarity.threshold = 0.85
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    class _FakeSimilarityService:
        def compute_similarities_detailed(self, candidate_pairs, threshold):
            assert threshold == 0.55
            return [
                {
                    "doc1_key": "a",
                    "doc2_key": "b",
                    "field_scores": {"name": 0.72},
                    "weighted_score": 0.70,
                },
                {
                    "doc1_key": "c",
                    "doc2_key": "d",
                    "field_scores": {"name": 0.91},
                    "weighted_score": 0.90,
                },
            ]

        def batch_fetch_documents(self, keys):
            return {
                "a": {"_key": "a", "name": "Acme"},
                "b": {"_key": "b", "name": "Acme Corp"},
                "c": {"_key": "c", "name": "Beta"},
                "d": {"_key": "d", "name": "Beta LLC"},
            }

    class _FakeVerifier:
        def __init__(self):
            self.store = type("Store", (), {"collection": "customers_llm_feedback"})()
            self.verifier = type("Inner", (), {"needs_verification": lambda self, score: 0.55 <= score < 0.80})()

        def verify(self, record_a, record_b, score, field_scores=None):
            assert record_a["_key"] == "a"
            assert record_b["_key"] == "b"
            assert field_scores["name"]["method"] == "jaro_winkler"
            return {
                "decision": "match",
                "confidence": 0.9,
                "llm_called": True,
                "score_override": 0.92,
            }

    monkeypatch.setattr(pipe, "_build_active_learning_verifier", lambda: _FakeVerifier())
    matches = pipe._run_similarity_with_active_learning(_FakeSimilarityService(), [("a", "b"), ("c", "d")])
    assert matches == [("a", "b", 0.92), ("c", "d", 0.9)]
    assert pipe._active_learning_stats["llm_calls"] == 1
    assert pipe._active_learning_stats["score_overrides"] == 1


def test_run_similarity_passes_transformers_to_batch_service(monkeypatch) -> None:
    cfg = _FakeConfig()
    cfg.similarity.field_weights = {"phone": 1.0}
    cfg.similarity.transformers = {"phone": ["digits_only"]}
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    captured = {}

    class _FakeSimilarityService:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def compute_similarities(self, candidate_pairs, threshold):
            assert candidate_pairs == [("a", "b")]
            assert threshold == 0.75
            return [("a", "b", 1.0)]

    import entity_resolution.core.configurable_pipeline as mod

    monkeypatch.setattr(mod, "BatchSimilarityService", _FakeSimilarityService)
    matches = pipe.run_similarity([{"doc1_key": "a", "doc2_key": "b"}])

    assert matches == [("a", "b", 1.0)]
    assert captured["field_transformers"] == {"phone": ["digits_only"]}


# ---------------------------------------------------------------------------
# Tests for #5 — BM25 blocking field resolution
# ---------------------------------------------------------------------------

class _FakeBM25Strategy:
    """Captures the fields passed to BM25BlockingStrategy for assertion."""
    captured: dict = {}

    def __init__(self, db, collection, search_view, search_field, blocking_field):
        _FakeBM25Strategy.captured = {
            "search_field": search_field,
            "blocking_field": blocking_field,
        }

    def generate_candidates(self):
        return [{"doc1_key": "a", "doc2_key": "b"}]


def test_bm25_reads_search_field_from_blocking_config(monkeypatch) -> None:
    """search_field / blocking_field explicit attrs take precedence."""
    import entity_resolution.core.configurable_pipeline as mod
    monkeypatch.setattr(mod, "BM25BlockingStrategy", _FakeBM25Strategy)

    blocking = _BlockingCfg(
        strategy="bm25",
        search_field="company_name",
        blocking_field="state",
    )
    cfg = _FakeConfig(blocking=blocking)
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    result = pipe.run_blocking()
    assert _FakeBM25Strategy.captured["search_field"] == "company_name"
    assert _FakeBM25Strategy.captured["blocking_field"] == "state"
    assert len(result) == 1


def test_bm25_falls_back_to_fields_list(monkeypatch) -> None:
    """Falls back to first/second entries in blocking.fields when explicit attrs absent."""
    import entity_resolution.core.configurable_pipeline as mod
    monkeypatch.setattr(mod, "BM25BlockingStrategy", _FakeBM25Strategy)

    blocking = _BlockingCfg(
        strategy="bm25",
        fields=["full_name", "city"],
        # search_field and blocking_field intentionally left None
    )
    cfg = _FakeConfig(blocking=blocking)
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    pipe.run_blocking()
    assert _FakeBM25Strategy.captured["search_field"] == "full_name"
    assert _FakeBM25Strategy.captured["blocking_field"] == "city"


def test_bm25_raises_if_no_search_field(monkeypatch) -> None:
    """Raises ValueError when neither search_field nor fields is provided."""
    import entity_resolution.core.configurable_pipeline as mod
    monkeypatch.setattr(mod, "BM25BlockingStrategy", _FakeBM25Strategy)

    blocking = _BlockingCfg(strategy="bm25")  # no fields, no search_field
    cfg = _FakeConfig(blocking=blocking)
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    with pytest.raises(ValueError, match="search_field"):
        pipe.run_blocking()


def test_vector_blocking_uses_config_and_records_preflight(monkeypatch) -> None:
    import entity_resolution.core.configurable_pipeline as mod

    captured = {}

    class _FakeVectorStrategy:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def check_embeddings_exist(self):
            return {"total": 10, "with_embeddings": 8, "coverage_percent": 80.0}

        def generate_candidates(self):
            return [{"doc1_key": "a", "doc2_key": "b", "similarity": 0.91}]

    monkeypatch.setattr(mod, "VectorBlockingStrategy", _FakeVectorStrategy)

    cfg = _FakeConfig(
        blocking=_BlockingCfg(
            strategy="vector",
            embedding_field="emb_field",
            similarity_threshold=0.81,
            limit_per_entity=7,
            blocking_field="state",
        ),
    )
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)
    pairs = pipe.run_blocking()

    assert len(pairs) == 1
    assert captured["embedding_field"] == "emb_field"
    assert captured["similarity_threshold"] == 0.81
    assert captured["limit_per_entity"] == 7
    assert captured["blocking_field"] == "state"
    assert pipe._embedding_preflight_stats["coverage_percent"] == 80.0


def test_lsh_blocking_uses_config_and_records_preflight(monkeypatch) -> None:
    import entity_resolution.core.configurable_pipeline as mod

    captured = {}

    class _FakeLSHStrategy:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def check_embeddings_exist(self):
            return {"total": 20, "with_embeddings": 20, "coverage_percent": 100.0, "embedding_dim": 384}

        def generate_candidates(self):
            return [{"doc1_key": "a", "doc2_key": "c", "method": "lsh"}]

    monkeypatch.setattr(mod, "LSHBlockingStrategy", _FakeLSHStrategy)

    cfg = _FakeConfig(
        blocking=_BlockingCfg(
            strategy="lsh",
            num_hash_tables=12,
            num_hyperplanes=10,
            random_seed=123,
        ),
        embedding=_EmbeddingCfg(embedding_field="from_embedding_cfg"),
    )
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)
    pairs = pipe.run_blocking()

    assert len(pairs) == 1
    assert captured["embedding_field"] == "from_embedding_cfg"
    assert captured["num_hash_tables"] == 12
    assert captured["num_hyperplanes"] == 10
    assert captured["random_seed"] == 123
    assert pipe._embedding_preflight_stats["embedding_dim"] == 384


def test_run_surfaces_embedding_preflight_in_results(monkeypatch) -> None:
    cfg = _FakeConfig(
        blocking=_BlockingCfg(strategy="vector"),
        embedding=_EmbeddingCfg(runtime="pytorch"),
    )
    pipe = ConfigurableERPipeline(db=_FakeDB(), config=cfg)

    monkeypatch.setattr(
        pipe,
        "_setup_embedding_runtime",
        lambda: {"enabled": True, "runtime": "pytorch", "resolved_provider": "pytorch"},
    )
    monkeypatch.setattr(
        pipe,
        "run_blocking",
        lambda: (
            setattr(pipe, "_embedding_preflight_stats", {"coverage_percent": 95.0})
            or []
        ),
    )

    out = pipe.run()
    assert out["blocking"]["embedding_preflight"]["coverage_percent"] == 95.0
    assert out["embedding"]["preflight"]["coverage_percent"] == 95.0

